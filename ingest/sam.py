"""Ingest SAM.gov opportunities into Snowflake RAW schema (date-based).

Pulls all opportunities posted within the configured window (with pagination),
deduplicates by noticeId, and loads into RAW.SAM_OPPORTUNITIES via MERGE.
Idempotent: re-running replaces existing rows by notice_id.

Usage:
    uv run --env-file .env python ingest/sam.py
"""
import os
import json
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta

import requests
import pandas as pd
from dotenv import load_dotenv
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas


# --- Setup ----------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# --- Configuration --------------------------------------------------------

SAM_API_KEY = os.environ.get("SAM_API_KEY")
if not SAM_API_KEY:
    raise RuntimeError("SAM_API_KEY not found in environment")

WINDOW_DAYS = 7       # how far back to pull
PAGE_SIZE = 1000       # SAM v2 API max per page
SAM_API_URL = "https://api.sam.gov/opportunities/v2/search"


# --- API helpers ----------------------------------------------------------

def fetch_opportunities(posted_from: str, posted_to: str) -> list[dict]:
    """Fetch all opportunities posted in the date window, paginating with retry-on-429.

    No NAICS filter — pulls every opportunity in the window regardless of code.
    """
    results = []
    offset = 0
    while True:
        params = {
            "api_key": SAM_API_KEY,
            "postedFrom": posted_from,
            "postedTo": posted_to,
            "limit": PAGE_SIZE,
            "offset": offset,
        }
        for attempt in range(5):
            r = requests.get(SAM_API_URL, params=params, timeout=60)
            if r.status_code == 429:
                # Capture diagnostic info — distinguishes burst-window vs daily-quota
                rate_headers = {
                    k: v for k, v in r.headers.items()
                    if k.lower() in {
                        "retry-after",
                        "x-ratelimit-limit",
                        "x-ratelimit-remaining",
                        "x-ratelimit-reset",
                    }
                }
                try:
                    body = r.json()
                except Exception:
                    body = r.text[:500]
                log.warning(
                    f"429 at offset {offset} (attempt {attempt + 1}/5). "
                    f"Headers: {rate_headers}. Body: {body}"
                )
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            r.raise_for_status()
            break
        else:
            raise RuntimeError(f"Exhausted retries at offset {offset}")

        data = r.json()
        records = data.get("opportunitiesData", [])
        total = data.get("totalRecords", 0)
        results.extend(records)
        log.info(f"  page at offset {offset}: fetched {len(records)} (running total {len(results)} of {total})")
        offset += PAGE_SIZE
        if offset >= total or not records:
            break
        time.sleep(0.5)
    return results


# --- Data shaping ---------------------------------------------------------

def extract_state(opp: dict) -> str | None:
    """Extract place-of-performance state code; SAM may shape this a few ways."""
    pop = opp.get("placeOfPerformance")
    if not pop:
        return None
    state = pop.get("state")
    if not state:
        return None
    if isinstance(state, dict):
        return state.get("code")
    return state  # sometimes returned as a bare string


def opps_to_dataframe(opps: list[dict]) -> pd.DataFrame:
    """Transform SAM opportunity dicts into a DataFrame for staging."""
    rows = [
        {
            "NOTICE_ID":         opp.get("noticeId"),
            "POSTED_DATE":       opp.get("postedDate"),
            "NAICS_CODE":        opp.get("naicsCode"),
            "NOTICE_TYPE":       opp.get("type"),
            "IS_ACTIVE":         opp.get("active") == "Yes",
            "RESPONSE_DEADLINE": opp.get("responseDeadLine"),
            "TYPE_OF_SET_ASIDE": opp.get("typeOfSetAsideDescription"),
            "STATE":             extract_state(opp),
            "RAW":               json.dumps(opp),  # stored as VARCHAR in staging, parsed in MERGE
        }
        for opp in opps
    ]
    df = pd.DataFrame(rows)
    log.info(f"Built DataFrame: {len(df)} rows, columns {list(df.columns)}")
    return df


# --- Snowflake DDL & DML --------------------------------------------------

CREATE_TARGET_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS RAW.SAM_OPPORTUNITIES (
    notice_id           VARCHAR(50),
    posted_date         DATE,
    naics_code          VARCHAR(10),
    notice_type         VARCHAR(50),
    is_active           BOOLEAN,
    response_deadline   TIMESTAMP_TZ,
    type_of_set_aside   VARCHAR(500),
    state               VARCHAR(10),
    raw                 VARIANT,
    ingested_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
"""

MERGE_FROM_STAGING_SQL = """
MERGE INTO RAW.SAM_OPPORTUNITIES target
USING (
    SELECT
        NOTICE_ID,
        TRY_TO_DATE(POSTED_DATE)                      AS POSTED_DATE,
        NAICS_CODE,
        NOTICE_TYPE,
        IS_ACTIVE,
        TRY_TO_TIMESTAMP_TZ(RESPONSE_DEADLINE)       AS RESPONSE_DEADLINE,
        TYPE_OF_SET_ASIDE,
        STATE,
        PARSE_JSON(RAW)                               AS RAW
    FROM RAW.SAM_OPPORTUNITIES_STAGING
) source
ON target.notice_id = source.NOTICE_ID
WHEN MATCHED THEN UPDATE SET
    posted_date       = source.POSTED_DATE,
    naics_code        = source.NAICS_CODE,
    notice_type       = source.NOTICE_TYPE,
    is_active         = source.IS_ACTIVE,
    response_deadline = source.RESPONSE_DEADLINE,
    type_of_set_aside = source.TYPE_OF_SET_ASIDE,
    state             = source.STATE,
    raw               = source.RAW,
    ingested_at       = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    notice_id, posted_date, naics_code, notice_type, is_active,
    response_deadline, type_of_set_aside, state, raw, ingested_at
) VALUES (
    source.NOTICE_ID, source.POSTED_DATE, source.NAICS_CODE, source.NOTICE_TYPE, source.IS_ACTIVE,
    source.RESPONSE_DEADLINE, source.TYPE_OF_SET_ASIDE, source.STATE, source.RAW, CURRENT_TIMESTAMP()
)
"""


# --- Main orchestration ---------------------------------------------------

def main():
    # 1. Pull from SAM API
    posted_from = (datetime.now() - timedelta(days=WINDOW_DAYS)).strftime("%m/%d/%Y")
    posted_to = datetime.now().strftime("%m/%d/%Y")
    log.info(f"Pulling SAM opportunities posted {posted_from} to {posted_to}")

    opps = fetch_opportunities(posted_from, posted_to)

    # Dedup defensively in case pagination returned overlap
    by_notice_id: dict[str, dict] = {}
    for opp in opps:
        nid = opp.get("noticeId")
        if nid:
            by_notice_id[nid] = opp

    log.info(f"Fetched {len(opps)} raw records, {len(by_notice_id)} unique by notice_id")
    if not by_notice_id:
        log.warning("No opportunities. Exiting without touching Snowflake.")
        return

    # 2. Connect to Snowflake
    log.info("Connecting to Snowflake...")
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema="RAW",
    )

    try:
        cur = conn.cursor()

        # 3. Ensure target table exists
        log.info("Ensuring RAW.SAM_OPPORTUNITIES exists...")
        cur.execute(CREATE_TARGET_TABLE_SQL)

        # 4. Load DataFrame to a staging table
        log.info("Writing to staging table RAW.SAM_OPPORTUNITIES_STAGING...")
        df = opps_to_dataframe(list(by_notice_id.values()))
        success, num_chunks, num_rows, _ = write_pandas(
            conn,
            df,
            table_name="SAM_OPPORTUNITIES_STAGING",
            schema="RAW",
            auto_create_table=True,
            overwrite=True,
        )
        if not success:
            raise RuntimeError("write_pandas reported failure")
        log.info(f"  staged {num_rows} rows in {num_chunks} chunks")

        # 5. MERGE staging into target (idempotent upsert)
        log.info("Merging staging into RAW.SAM_OPPORTUNITIES...")
        cur.execute(MERGE_FROM_STAGING_SQL)
        log.info(f"  MERGE complete: {cur.rowcount} rows affected")

        # 6. Clean up staging
        cur.execute("DROP TABLE IF EXISTS RAW.SAM_OPPORTUNITIES_STAGING")

        # 7. Verify
        cur.execute("SELECT COUNT(*) FROM RAW.SAM_OPPORTUNITIES")
        target_count = cur.fetchone()[0]
        log.info(f"Final RAW.SAM_OPPORTUNITIES row count: {target_count}")

        cur.close()
    finally:
        conn.close()

    log.info("Done.")


if __name__ == "__main__":
    main()