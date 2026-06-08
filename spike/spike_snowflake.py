"""Spike: verify Snowflake connectivity from local Python."""
import os
from pathlib import Path

import snowflake.connector
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    role=os.environ["SNOWFLAKE_ROLE"],
    warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
    database=os.environ["SNOWFLAKE_DATABASE"],
    schema=os.environ["SNOWFLAKE_SCHEMA"],
)

cur = conn.cursor()
cur.execute("SELECT CURRENT_VERSION(), CURRENT_USER(), CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()")
row = cur.fetchone()
print("Snowflake version:   ", row[0])
print("Connected as user:   ", row[1])
print("Active role:         ", row[2])
print("Active warehouse:    ", row[3])
print("Active database:     ", row[4])
print("Active schema:       ", row[5])

# small smoke test of compute
cur.execute("SELECT COUNT(*) FROM TABLE(GENERATOR(ROWCOUNT => 1000000))")
print(f"\nSmoke test: counted {cur.fetchone()[0]:,} generated rows")

cur.close()
conn.close()
print("\nConnection closed cleanly.")