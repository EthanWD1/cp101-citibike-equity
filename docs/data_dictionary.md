# Data definitions and interpretation

## Keys, geography, and provenance

- `station_id`: original string ID; leading zeros and decimal punctuation are preserved. No station is inferred from an ID-free coordinate.
- `GEOID`: eleven-character Census tract identifier: state (2) + county (3) + tract (6). NYC state is 36; county codes are 005 (Bronx), 047 (Brooklyn/Kings), 061 (Manhattan/New York), 081 (Queens), and 085 (Staten Island/Richmond).
- Station source coordinates are longitude/latitude in EPSG:4326. Spatial joins use **EPSG:32618**; distances are meters. The tract GeoPackage retains that projected CRS.
- The data manifest preserves the provider URLs and SHA-256 checksums. Raw data are unchanged. The trip archive contains six CSVs, read in lexicographic filename order.

## ACS fields

| Output | Summary-file estimate / MOE | Meaning / units |
|---|---|---|
| `income`, `income_moe` | B19013_E001 / B19013_M001 | Median household income, 2024 inflation-adjusted dollars; 90% margin of error |
| `households`, `households_moe` | B08201_E001 / B08201_M001 | Total households; 90% margin of error, households |
| `no_vehicle_households`, `no_vehicle_households_moe` | B08201_E002 / B08201_M002 | Households with no vehicle available; 90% margin of error, households |
| `population`, `population_moe` | B01003_E001 / B01003_M001 | Total population; 90% margin of error, people |
| `no_vehicle_share` | B08201_E002 / B08201_E001 | Fraction from 0 to 1; figures express it as a percentage |

Every estimate and MOE has a `_raw` string and `_annotation` field. Negative ACS sentinel values and nonnumeric suppression tokens are unavailable, not zero. Upper/lower income category codes (250001/2499, or explicit +/- labels) are represented at $250,000/$2,500 and flagged as censored; they are not treated as exact medians. `income_imprecise` flags a reported MOE greater than 50% of the estimate, an analyst-selected screening rule that does not exclude a tract. Missing MOEs do not imply precision. No error bars or significance claims are derived from the retained MOEs.

Official definitions: [ACS table shells](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/documentation/ACS20245YR_Table_Shells.txt), [B19013](https://api.census.gov/data/2024/acs/acs5/groups/B19013.html), [B08201](https://api.census.gov/data/2024/acs/acs5/groups/B08201.html), [B01003](https://api.census.gov/data/2024/acs/acs5/groups/B01003.html), and [ACS technical documentation](https://www.census.gov/programs-surveys/acs/technical-documentation/code-lists.html).

## Tract metrics

| Field | Definition |
|---|---|
| `eligible` | Positive, available households, population, and land area |
| `land_km2` | TIGER ALAND (square meters) / 1,000,000 |
| `observed_stations` | Distinct station IDs observed at either endpoint of retained September-start trips and spatially assigned to this tract |
| `departures` | Retained September starts with a valid station ID whose canonical location maps to this tract |
| `stations_per_km2` | Observed stations / land km² |
| `stations_per_10000` | 10,000 × observed stations / ACS population |
| `departures_per_station` | September departures / observed stations; missing when station count is zero |
| `income_quartile`, `no_vehicle_quartile` | Q1 ≤ citywide p25; Q2 ≤ p50; Q3 ≤ p75; Q4 > p75; computed on eligible tracts with the relevant variable |

The thresholds in `validation.json` are numerical; no borough-specific recutting occurs. Ties can yield unequal or empty quartiles. Censored income values remain tied at the reported boundary in quartile and Spearman calculations. All comparisons are descriptive and unweighted across tracts.

## Audit outputs

- `trip_file_audit.csv`: input counts and disjoint trip exclusions per original CSV.
- `raw_date_category_audit.csv`: all input rows, missing ride IDs, invalid start times, and out-of-September starts by parsed date and rider category, before deduplication. Unparseable dates get their own category.
- `cleaning_ledger.csv`: before/affected/after counts, action, and reason at each stage. Endpoint flags overlap; they are not extra discarded trips.
- `missingness_by_date_category.csv`: missing IDs, unusable coordinates, and invalid end times among retained September starts, by date and member/casual/unknown category.
- `station_coordinate_audit.csv`: every observed valid station/coordinate pair, endpoint count, and distance to its ID's modal coordinate.
- `station_location_flags.csv`: IDs with a maximum displacement greater than 100 m. The flag is a review threshold, not a relocation rule.
- `unmatched_stations.csv`: observed station points that do not intersect an NYC tract. This includes out-of-area points and possible coordinate/boundary problems; it is not automatically labeled New Jersey.
- `unassigned_station_departures.csv`: starts with station IDs but no NYC tract assignment, including IDs for which no usable coordinates are available anywhere in the retained endpoint observations.
- `coordinate_only_starts.csv`: starts without a station ID but with usable coordinates, aggregated by coordinate/day/category and spatially labeled separately. These do not enter station counts or per-station usage.
- `station_daily_departures.csv`: start station × date × rider category counts with tract/borough assignment where available.
- `borough_summary.csv`: coverage and usage summaries, distinguishing all NYC tracts from eligible residential tracts.
- `quartile_comparisons.csv`: group sizes, served-tract counts, zero-station percentages, and distributions of all three metrics.
- `spearman_correlations.csv`: citywide and within-borough rank associations, sample sizes, and explicit undefined cases. No inferential p-values are reported.
- `validation.json`: reconciliation checks, headline counts, thresholds, software versions, and runtime.

## Limits

No observed station is not proof of no service, and low within-tract density is not a walking-access measure. Stations across tract boundaries may be nearby. One month does not measure annual demand or continuous operation. A missing destination does not invalidate a departure; a missing start coordinate can be recovered through a valid station ID's other observations. The station inventory is therefore an observation-based reconstruction, not an official operating inventory or dock-capacity measure.

ACS describes 2020–2024 households, not September 2025 riders. Visitors and commuters can use stations. Income, vehicle access, jobs, land use, transit, and cycling infrastructure can be related to station placement and activity; within-borough comparisons do not control for these factors. Coordinate uncertainty, partial-month exposure, ACS uncertainty, and tract boundary choices remain subjects for the final-project sensitivity analysis.
