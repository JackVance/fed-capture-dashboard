"""Spike: verify USAspending returns recognizable contract data for our NAICS."""
import csv
import json
from pathlib import Path
from datetime import date, timedelta

import requests

PROJECT_ROOT = Path(__file__).parent.parent

# load NAICS from seed
NAICS_FILE = PROJECT_ROOT / "seeds" / "target_naics.csv"
with NAICS_FILE.open() as f:
    reader = csv.DictReader(f)
    TARGET_NAICS = [row["naics_code"] for row in reader]
print(f"Loaded {len(TARGET_NAICS)} NAICS codes from {NAICS_FILE}")

# 2-year window
TODAY = date.today()
START_DATE = (TODAY - timedelta(days=730)).isoformat()
END_DATE = TODAY.isoformat()

# A=BPA Call, B=Purchase Order, C=Delivery Order, D=Definitive Contract
# (skipping IDV types and grants/cooperative agreements for now)
CONTRACT_AWARD_TYPES = ["A", "B", "C", "D"]

payload = {
    "filters": {
        "time_period": [{"start_date": START_DATE, "end_date": END_DATE}],
        "award_type_codes": CONTRACT_AWARD_TYPES,
        "naics_codes": TARGET_NAICS,
    },
    "fields": [
        "Award ID",
        "Recipient Name",
        "Recipient UEI",
        "Award Amount",
        "Awarding Agency",
        "Awarding Sub Agency",
        "NAICS Code",
        "Description",
        "Start Date",
        "End Date",
    ],
    "sort": "Award Amount",
    "order": "desc",
    "limit": 100,
    "page": 1,
}

print(f"Querying USAspending awards")
print(f"  NAICS:  {TARGET_NAICS}")
print(f"  Window: {START_DATE} to {END_DATE}")
print(f"  Award types: {CONTRACT_AWARD_TYPES}\n")

r = requests.post(
    "https://api.usaspending.gov/api/v2/search/spending_by_award/",
    json=payload,
    timeout=60,
)
r.raise_for_status()
data = r.json()

results = data.get("results", [])
meta = data.get("page_metadata", {})

print(f"Returned this page: {len(results)}")
print(f"Total available: {meta.get('total', '?')}\n")

# top recipients in this page (page is sorted by amount desc, so this is top by single-award value)
print("Top 20 awards (by single-award amount):")
for award in results[:20]:
    amt = award.get("Award Amount") or 0
    rec = award.get("Recipient Name") or "?"
    naics = award.get("NAICS Code") or "?"
    desc = (award.get("Description") or "")[:50]
    print(f"  ${amt:>14,.0f}  [{naics}]  {rec:<40}  {desc}")
print()

# aggregate by recipient across the page
from collections import defaultdict
vendor_totals = defaultdict(lambda: {"total": 0, "count": 0})
for award in results:
    name = award.get("Recipient Name") or "?"
    vendor_totals[name]["total"] += award.get("Award Amount") or 0
    vendor_totals[name]["count"] += 1

print("Top 20 recipients by total obligation (this page only):")
top_vendors = sorted(vendor_totals.items(), key=lambda x: -x[1]["total"])[:20]
for name, stats in top_vendors:
    print(f"  ${stats['total']:>14,.0f}  ({stats['count']:>3} awards)  {name}")
print()

# look for Federal Strategies specifically
fs_matches = [a for a in results if "federal strategies" in (a.get("Recipient Name") or "").lower()]
if fs_matches:
    print(f"Found {len(fs_matches)} Federal Strategies award(s) in this page:")
    for award in fs_matches:
        print(f"  ${award.get('Award Amount') or 0:>14,.0f}  {award.get('Recipient Name')}  [{award.get('NAICS Code')}]")
else:
    print("No Federal Strategies awards in top 100 by amount.")
    print("(That's expected — they're a smaller vendor; the page is sorted by largest first.)")
    print("In the real ingestion we'd paginate to find them, or query by recipient UEI directly.")
print()

# save raw response for inspection
out = PROJECT_ROOT / "spike" / "usaspending_sample.json"
out.write_text(json.dumps(data, indent=2))
print(f"Raw response saved to {out}")