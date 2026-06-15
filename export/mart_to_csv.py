"""Export MART_OPPORTUNITIES to CSV for Tableau Public consumption.

Tableau Public can't connect to Snowflake directly, so we export the mart as
a flat CSV that Tableau loads as a file-based data source. Re-run this script
to refresh the dashboard's data.

Usage:
    uv run --env-file .env python export/mart_to_csv.py
"""
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
import snowflake.connector


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

OUTPUT_DIR = PROJECT_ROOT / "exports"
OUTPUT_FILE = OUTPUT_DIR / "mart_opportunities.csv"

EXPORT_QUERY = """
SELECT *
FROM FED_CAPTURE.MARTS.MART_OPPORTUNITIES
"""


# --- Main -----------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    log.info("Connecting to Snowflake...")
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_READER_USER"],
        password=os.environ["SNOWFLAKE_READER_PASSWORD"],
        role=os.environ["SNOWFLAKE_READER_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema="MARTS",
    )

    try:
        cur = conn.cursor()

        log.info("Querying MART_OPPORTUNITIES...")
        cur.execute(EXPORT_QUERY)
        df = cur.fetch_pandas_all()
        log.info(f"Fetched {len(df)} rows, {len(df.columns)} columns")

        log.info(f"Writing to {OUTPUT_FILE.relative_to(PROJECT_ROOT)}...")
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")

        size_kb = OUTPUT_FILE.stat().st_size / 1024
        log.info(f"  wrote {size_kb:.1f} KB ({len(df)} rows)")

        cur.close()
    finally:
        conn.close()

    log.info(f"Done. CSV available at: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()