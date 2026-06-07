# -*- coding: utf-8 -*-
"""
Created on Fri Jun  5 16:21:49 2026

@author: jackv
"""

"""Spike: verify SAM.gov Opportunities API returns usable data for our NAICS."""
import os
import csv
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

import requests
from dotenv import load_dotenv

# run relative to root directory
PROJECT_ROOT = Path(__file__).parent.parent

load_dotenv(PROJECT_ROOT / ".env")

# get api key
API_KEY = os.environ.get("SAM_API_KEY")
if not API_KEY:
    raise RuntimeError("SAM_API_KEY not found. Check .env in project root.")

# get list of NAICS codes
NAICS_FILE = PROJECT_ROOT / "seeds" / "target_naics.csv"
with NAICS_FILE.open() as f:
    reader = csv.DictReader(f)
    TARGET_NAICS = [row["naics_code"] for row in reader]
print(f"Loaded {len(TARGET_NAICS)} NAICS codes from {NAICS_FILE}")

POSTED_FROM = (datetime.now() - timedelta(days=90)).strftime("%m/%d/%Y")
POSTED_TO = datetime.now().strftime("%m/%d/%Y")

print(f"Querying SAM.gov opportunities")
print(f"  NAICS:  {TARGET_NAICS}")
print(f"  Window: {POSTED_FROM} to {POSTED_TO}\n")

# SAM.gov ncode filter doesn't reliably handle multi-value; loop per NAICS and dedup
all_opps = {}  # noticeId -> opp (auto-dedups across NAICS)

for code in TARGET_NAICS:
    params = {
        "api_key": API_KEY,
        "postedFrom": POSTED_FROM,
        "postedTo": POSTED_TO,
        "ncode": code,
        "limit": 100,
    }
    r = requests.get(
        "https://api.sam.gov/opportunities/v2/search",
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    total = data.get("totalRecords", 0)
    returned = len(data.get("opportunitiesData", []))
    print(f"  NAICS {code}: totalRecords={total}, returned this page={returned}")
    for opp in data.get("opportunitiesData", []):
        nid = opp.get("noticeId")
        if nid:
            all_opps[nid] = opp

opps = list(all_opps.values())
print(f"\nUnique opportunities across all NAICS: {len(opps)}\n")

types = Counter(opp.get("type") for opp in opps)
print("Notice type breakdown:")
for t, n in types.most_common():
    print(f"  {n:>4}  {t}")
print()

print("Sample opportunities (first 10):")
for opp in opps[:10]:
    title = (opp.get("title") or "")[:80]
    dept = opp.get("department") or "?"
    print(f"  [{opp.get('type'):<25}] {title}  ({dept})")
print()

out = PROJECT_ROOT / "spike" / "sam_sample.json"
out.write_text(json.dumps(opps, indent=2))
print(f"Raw response saved to {out}")