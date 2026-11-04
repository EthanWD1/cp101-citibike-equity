# Group PAIR midterm report

Timothy Phan and Ethan Deng · Revised November 3, 2026 · Track B



## Research question and status

How did observed Citi Bike station density and usage vary with median household income and the share of households without a vehicle across New York City census tracts in September 2025, citywide and within each borough? The geography, month, demographic variables, and descriptive approach remain as proposed. The audience is NYC transportation planners and community groups assessing where observed coverage merits closer review.



Completed: full-month acquisition, documented cleaning, point-to-tract spatial join, citywide/borough comparisons, one map and five charts, and a reproducible Python workflow. Static figures are the midterm milestone. Animated maps, the webpage, and operational/boundary sensitivity checks remain final-project work; no historical station inventory has been replaced by a current feed.



## Data and cleaning

All six original trip CSVs contain 5,287,447 rows. ACS 2020–2024 five-year tables B19013 (income), B08201 (households/vehicle availability), and B01003 (population) supply tract context; 2024 TIGER/Line supplies boundaries and land area. ACS data were obtained from official table-based text files without an API key. Raw files, download dates, URLs, and SHA-256 checksums are retained.



The sequential trip filters remove 931 starts outside September; missing ride IDs, duplicate IDs, and invalid start timestamps each affect 0, 0, and 0 rows, respectively. Of 5,286,516 retained starts, 2,118 lack both a start station ID and usable coordinates and cannot enter station usage. Missing destination IDs affect 12,865 retained trips but do not remove their valid departures.



The spatial join assigns 2,212 of 2,269 located station IDs to NYC; 57 station locations outside/unmatched to NYC remain audited. There are 0 boundary ties. Residential comparisons retain 2,231 of 2,327 NYC tracts; 96 fail the positive-household/population/land-area rule. Another 32 eligible tracts lack income and remain mapped but are excluded only from income comparisons. The 13 upper-bound income estimates are flagged; 272 eligible tracts have income MOEs above half their estimate.



## Methods

1. Parse local timestamps, keep September starts, and deduplicate ride IDs across files using a disk-backed index. 2. Infer station locations from both endpoints by modal coordinate pair, preserving string IDs. 3. Project to EPSG:32618 (meters), spatially intersect stations with tracts, and merge ACS by eleven-digit GEOID. 4. Aggregate starts by their station's tract; calculate stations/land km², stations/10,000 residents, and departures/observed station. 5. Compare unweighted tracts using fixed citywide income and no-vehicle-share quartiles within every borough; report descriptive Spearman correlations. Coverage includes zeros; usage excludes zero-station tracts. Land area is TIGER ALAND/1,000,000, excluding water from the denominator.



## Early results

Observed coverage is uneven: 1,335 of 2,231 eligible tracts (59.8%) have no observed station. The share is 11.6% in Manhattan, 72.9% in Queens, and 100% in Staten Island. These are observations from trip records, not a claim that residents cannot reach stations in adjacent tracts.



The citywide income–density correlation is nearly flat (ρ=0.05), but borough patterns differ: Bronx -0.53, Brooklyn 0.30, Manhattan 0.05, and Queens -0.13. No-vehicle household share is more positively associated with density citywide (ρ=0.59). Its highest quartile has 21.9% zero-station tracts, versus 95.5% in its lowest quartile. The borough differences caution against a single citywide income story.



Among tracts with stations, median September departures per observed station rise from 496 in the lowest income quartile to 4,068 in the highest. This conditional comparison describes activity where stations were observed, not demand in unserved tracts or trips made by residents. Casual departures averaged 41,897/day on weekends versus 30,249 on weekdays this month; no causal explanation is established.



## Limitations

ACS estimates cover five years and have sampling uncertainty; they do not describe individual riders. Tract boundaries, jobs, transit, land use, and partial-month operation can affect the patterns. The one flagged station location spans 291 m; its modal pair accounts for 383 of 389 endpoint observations, and both locations fall in the same tract. We retain the modal location with no manual override. Low observed density is not a direct walking-access measure, and low usage does not establish low or unmet demand.



## Plan to finish

Ethan · Nov 16: review land/population normalization and boundary effects; repeat usage comparisons for stations observed in both first and last weeks. Tim · Dec 6: build the two interactive maps, daily animations, fixed scales, borough filters, and GitHub Pages draft. Both · Dec 15: review interpretation, rerun the workflow, and finalize. Main risks are uncertain exposure, ACS precision, and map performance; use sensitivity checks and aggregated layers rather than adding causal claims or rendering individual trips.



We would appreciate feedback on three questions: (1) How should we account for stations just outside a tract when discussing residents' access? (2) Are comparisons by borough enough at this stage, or should we do more to address uncertainty in the ACS estimates and differences in land use? (3) Would comparing stations observed in both the first and last weeks help us account for stations that may have operated for only part of September?



## Reproducibility and figures

Repository: https://github.com/EthanWD1/cp101-citibike-equity

The report embeds figures 01 and 06; figures 02–05 and complete comparison tables accompany the PDF. All six figures have titles, units, sources, and captions.

Figure 01 subtracts 2024 Census Area Hydrography only from display geometry; original tracts, spatial joins, and TIGER ALAND denominators are unchanged. Figures 02–03 show medians, middle-50% intervals, zero-station percentages, and tract counts on a linear density scale. Figure 04 shows usage medians and contributing-tract counts, flags n<5, and distinguishes undefined usage. Figure 05 retains all observations and flags censored income. Figure 06 shades weekends and labels rider categories directly.

Official source links and data-use terms are listed in README.md and data/raw/sources.json.
