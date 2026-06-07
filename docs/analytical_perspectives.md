# Analytical Perspectives — Federal Capture Intelligence

Notes capturing the analytical surfaces this project should support, beyond
the basic "vendor profile + open opportunities" loop. Each perspective is
mapped to the dbt mart(s) that will deliver it. V1 priorities are listed
first; V2+ refinements follow.

## V1 Priority Perspectives

### 1. Vendor Profile (backward-looking)

For a selected recipient (by UEI, with parent rollup), compute:

- Total obligations over selectable time window
- Year-over-year revenue trend
- Award count and average award size
- NAICS distribution (industries the vendor positions itself under)
- PSC distribution (what the vendor actually delivers)
- Awarding agency mix and sub-agency concentration
- Set-aside qualifications and how often used
- Top customer relationships by repeat-business

**Mart:** `mart_vendor_scorecard`
**Data:** USAspending File D1 (contracts), File E (recipient attributes)
**Entity resolution gotcha:** name variants like "X LLC" vs. "X, LLC" need
canonical UEI matching, not string matching. Surface ambiguity to the user
rather than auto-merging.

### 2. Recompete Forecasting (forward-looking)

For each historical contract, project the next likely recompete window from:

- Period of performance end date
- Option year structure (IDV vs definitive contract)
- Modification history (extensions, exercised options)

Surface as a calendar of upcoming recompetes, sized by potential value,
filterable by NAICS / agency / incumbent. This is the most differentiated
analytical surface vs. just browsing SAM.gov — it tells you what will be
competed 12-24 months out.

**Mart:** `mart_recompete_calendar`
**Data:** USAspending File D1 with period-of-performance fields
**Caveat:** modification patterns are messy, especially DoD services contracts.
Calibrate projections against actual recompete outcomes when available.

### 3. Set-Aside Qualification Matching

Federal opportunities are often restricted to specific business categories.
Filter the live opportunity pipeline to ones the user's company actually
qualifies for, instead of bidding wastefully on contests they can't win.

Set-aside types to support:
- SBA (Small Business)
- 8(a) and 8(a) Sole Source
- HUBZone
- SDVOSB (Service-Disabled Veteran-Owned Small Business)
- WOSB / EDWOSB (Women-Owned / Economically Disadvantaged WOSB)
- Native American
- Unrestricted (full and open competition)

**Mart:** `mart_open_opportunities` with set-aside filter dimension
**Data:** SAM.gov `typeOfSetAside` field on opportunities + SAM.gov entity
registration data for the vendor's qualifications

### 4. Contract Vehicle Leverage

Many federal contracts are task orders under large IDIQ vehicles
(SeaPort-NxG, OASIS, GSA Schedules, GWACs like Alliant 2). A vendor on the
vehicle competes for task orders under it; vendors off the vehicle can't bid
regardless of capability.

Capture:
- Which vehicles the target vendor holds positions on
- Filter opportunities to "competable via vehicles we hold"
- Identify high-value vehicles where adding a position would expand opportunity surface

**Mart:** `mart_vehicle_coverage`
**Data:** USAspending `parent_award_piid` linking task orders to parent IDIQs
**Note:** also a useful proxy for "what level of relationship does the vendor
have with the agency" — vehicle awards are competitive selections in their own
right.

### 5. Sub-Award Flow Analysis

Primes farm work out to subs. A vendor active as a sub has revenue dependent
on which primes pull them in; understanding the prime network tells you which
relationships to cultivate.

- For target vendor: which primes have they subbed to, on what types of work
- For target primes: which subs do they consistently use
- Network graph of prime-sub relationships in the target NAICS/PSC slice

**Mart:** `mart_subaward_network`
**Data:** USAspending File F (Sub-Award Reporting from FSRS)
**Caveat:** sub reporting is required only above thresholds and is widely
under-reported. Treat sub data as suggestive, not authoritative.

## V2+ Specialized Perspectives

### Customer Concentration Risk

Diversification health metric: percentage of vendor revenue from top-1, top-3,
top-5 sub-agencies. High concentration = vulnerability if any single customer
relationship sours. Also useful for screening acquisition targets.

### Modification Ratio

Current contract value ÷ initial obligated value. Measures expand-existing-business
muscle vs. new-business muscle. High mod ratios in DoD services suggest the
vendor is good at scope creep capture, an underrated revenue lane.

### PSC vs NAICS Mix Divergence

Compares what the vendor's NAICS profile claims they "do" vs. what their PSC
profile shows they actually deliver. Mismatches surface untapped capability
positioning or NAICS under-registration in SAM.

### Win-Loss Inference (Interested Vendors List)

When opportunities publish bidder lists (Interested Vendors), can infer
competitive outcomes by joining bid roster to eventual awardee. Reveals
head-to-head competitive patterns over time.

### Fiscal Year Timing Patterns

Federal Q4 (July-Sept) is the obligation crunch. Visualize award activity by
fiscal quarter to inform capacity planning and bid-and-proposal investment
timing.

### Geographic Concentration

Place of performance vs. recipient HQ location. Implications for cost basis
(labor rates by region), clearance pool depth, and travel cost overhead.

## Mapping to Project Architecture

| Perspective | Primary Mart(s) | Data Source(s) |
|---|---|---|
| Vendor Profile | mart_vendor_scorecard | USAspending File D1, E |
| Recompete Forecasting | mart_recompete_calendar | USAspending File D1 |
| Set-Aside Matching | mart_open_opportunities | SAM.gov + SAM entity reg |
| Vehicle Leverage | mart_vehicle_coverage | USAspending File D1 |
| Sub-Award Network | mart_subaward_network | USAspending File F |
| Customer Concentration | mart_vendor_scorecard (extension) | USAspending File D1 |
| Modification Ratio | mart_vendor_scorecard (extension) | USAspending File D1 |
| Win-Loss Inference | mart_competitive_intel | SAM.gov + FPDS |

## References

- USAspending Data Dictionary: https://www.usaspending.gov/data-dictionary
- SAM.gov Opportunity API: https://open.gsa.gov/api/get-opportunities-public-api/
- FPDS-NG (contract-level data source): https://www.fpds.gov
- SBA NAICS Size Standards: https://www.sba.gov/document/support-table-size-standards
- PSC Manual (acquisition.gov): https://www.acquisition.gov/psc-manual
- FFATA Sub-Award Reporting: https://www.fsrs.gov

---

*Last updated: <add date when you edit>. This document is forward-looking; not
all perspectives are implemented in the current build.*