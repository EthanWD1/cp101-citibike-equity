# Citi Bike station density and neighborhood mobility

**Group PAIR · Timothy Phan and Ethan Deng · CYPLAN 101 · Track B**

How did observed Citi Bike station density and usage vary with median household income and the share of households without a vehicle across New York City census tracts in September 2025, citywide and within each borough?

This repository contains the midterm analysis, a three-page report, an executed notebook, one map, and five charts. It processes the **complete September archive**, including all six CSVs. Findings describe associations between tract characteristics and observed stations/activity; they do not identify riders' household characteristics or estimate causal effects.

## Read the deliverables

- [Midterm report](Group_PAIR_midterm.pdf)
- [Executed analysis notebook](notebooks/midterm_analysis.ipynb)
- [Early findings](docs/early_results.md)
- [Cleaning counts and validation](docs/cleaning_audit.md)
- [Submission verification](docs/verification.md)
- [Data definitions and methodological decisions](docs/data_dictionary.md)
- [Figures and captions](visualizations/)
- [Original team proposal](docs/Group_PAIR_proposal.pdf)

## Setup and execution

Tested with **Python 3.13.12**. Create an isolated environment from the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate` instead. The download command needs `curl` on PATH. No Census API key is needed.

```bash
python -m analysis.download_data
python -m analysis.pipeline
```

The first command downloads the original trip ZIP (1,032,411,368 bytes), New York tract ZIP, three national ACS table files, and five small NYC county water ZIPs. It records URLs, UTC retrieval timestamps, sizes, and SHA-256 checksums in `data/raw/sources.json`. Rerunning verifies existing sources instead of downloading them again. A changed checksum is an error that must be investigated.

The second command verifies inputs, processes all trips in chunks, regenerates processed data, makes all six figures, and builds the PDF from the editable Markdown report. **It does not need internet access.** The Gradescope ZIP already includes all raw inputs, so skip acquisition when running that copy. Allow about 5 GB free disk space for inputs, the SQLite deduplication index, outputs, and packaging. Download time depends on the connection; analysis timing for the tested machine is recorded in `data/processed/validation.json`. Chunk size defaults to 200,000; lower it with `--chunk-size 50000` if necessary.

For an interactive notebook, select this environment's Python kernel and run **Kernel → Restart & Run All**. The notebook works from the root or `notebooks/`, calls the same reusable functions, and regenerates the analysis rather than depending on stale outputs. To execute it automatically in a new kernel with external network connections disabled:

```bash
python -m analysis.execute_notebook
```

For numerical, spatial, and Markdown-to-PDF checks (including PDF inspection dependencies):

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

To revise figures without reprocessing trips, regenerate them from existing processed tables and reconcile all plotted summaries:

```bash
python -m analysis.visualize
python -m analysis.verify_figures
python -m analysis.report
```

The full pipeline and notebook perform the same figure checks automatically. Run the full notebook after finalizing figure changes so its embedded images remain current.

The repository uses relative project paths. The original proposal is preserved. This is a midterm analysis repository; animated maps and GitHub Pages remain final-project work.

## Editing the write-up

Edit **`docs/report_source.md`**, save it, then run from the project root:

```bash
.venv/bin/python -m analysis.report
```

This compiles `Group_PAIR_midterm.pdf` without rerunning trip processing or overwriting your Markdown. The pipeline also reads this same Markdown file and preserves your edits. Keep the three `#` page titles and the `<!-- table: ... -->` markers; the latter insert the current cleaning and borough tables. Image paths are relative to the Markdown file. You can use paragraphs, `##` headings, bold, italics, links, and simple bullet/numbered lists. The short editing comment at the top is omitted from the PDF.

The compiler checks the three-page limit. If a page is too long, it identifies that page and keeps the previous PDF so you can shorten the text and try again. Tables load the latest processed data, but numbers you write in the narrative remain editable text: check them against the results if you change the data or analysis. `docs/early_results.md` remains a separately generated notebook summary; editing the report does not rewrite notebook commentary.

After checking the PDF, refresh your submission archive:

```bash
.venv/bin/python -m analysis.package_submission
```

## Source data

| Dataset | Coverage / granularity | Type and format | Official source / terms |
|---|---|---|---|
| Citi Bike trip histories | September 2025 starts; individual trips; stations assigned spatially to NYC | Tabular CSVs in original ZIP | [System data](https://citibikenyc.com/system-data), [archive](https://s3.amazonaws.com/tripdata/202509-citibike-tripdata.zip), [NYCBS data policy](https://citibikenyc.com/data-sharing-policy) |
| ACS five-year detailed tables | 2020–2024; NYC census tracts selected from national files | Pipe-delimited text, estimates and margins of error | [Summary file documentation](https://www.census.gov/programs-surveys/acs/data/summary-file.2024.html), [official files](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/) |
| TIGER/Line tracts | 2024 New York, filtered to Bronx, Kings, New York, Queens, Richmond counties | Polygon shapefile in ZIP | [Original tract ZIP](https://www2.census.gov/geo/tiger/TIGER2024/TRACT/tl_2024_36_tract.zip) |
| TIGER/Line Area Hydrography | 2024 water polygons for the five NYC counties; display only | Five polygon shapefile ZIPs, 355 KB total | [Official Area Hydrography directory](https://www2.census.gov/geo/tiger/TIGER2024/AREAWATER/) |

Census-produced data are generally not copyrighted in the United States; see the [Census data policy](https://www2.census.gov/foia/ds_policies/ds027.pdf). Citi Bike data retain their source terms. The original trip archive is included as source material in the noncommercial course submission, not published here as a standalone dataset. Download it from the provider to reproduce a GitHub clone. No rider identification is attempted.

## Analysis decisions

1. Deduplicate ride IDs across chunks and files with a disk-backed SQLite index. Keep the first row in sorted CSV-name and original row order, then filter start timestamps to September. Missing/invalid start times and missing ride IDs are excluded with counts. Missing destinations do not remove valid departures.
2. Identify stations from valid start and end endpoint coordinates, preserving IDs as strings. Choose each ID's most frequent exact coordinate pair; break ties by ascending latitude, then longitude. Flag IDs whose coordinates extend more than 100 m from that location. The raw observations and flags remain available for review.
3. Project to WGS 84 / UTM zone 18N (**EPSG:32618**, meters). Spatially intersect station points with NYC tracts. Exact shared-boundary ties go to the first GEOID and are flagged; unmatched points are not snapped. Departures inherit the start station's assigned tract, counting interborough trips once.
4. Merge ACS using eleven-digit GEOIDs. Use B19013_001E for median income, B08201_002E / B08201_001E for no-vehicle household share, and B01003_001E for population. Summary-file names use E001/M001 rather than the API's 001E/001M ordering. Retain raw tokens, estimate/MOE annotations, and censored-income flags.
5. Compare all eligible residential tracts with positive households, population, and land area. Count zero observed stations as zero coverage; usage stays undefined without stations. Keep ineligible tracts in the spatial output and map with a separate symbol. Tracts missing one grouping variable remain in other comparisons.
6. Use fixed citywide 25th/50th/75th percentile cutpoints within every borough. Equal values are not split to force equal-sized groups. Report tract counts, zero-station percentages, density distributions, usage medians, and descriptive Spearman correlations. Each tract receives equal weight. Empty/constant groups have undefined correlations.

Area normalization uses **TIGER ALAND / 1,000,000**, not polygon area including water. Population normalization is stations per 10,000 ACS residents. September usage is departures per observed station, not trips per station-day. Daily totals include NYC stations in both eligible and ineligible tracts; the audit explicitly reconciles that difference.

## Reading the figures

The November 3 revision preserves every analytical result and improves the six static figures:

- **01 — Coverage map:** a display-only shoreline mask removes water from the original tracts. Density colors remain visible without a station-dot overlay; zero stations and ineligible tracts have distinct symbols. Original geometries, station assignments, and land-area denominators remain unchanged. The same positive-density quartile breaks are retained.
- **02–03 — Density comparisons:** dots show medians and lines show the middle 50% of tracts on a common 0–60 stations/km² scale. Each row gives its no-station percentage and eligible-tract count with the relevant demographic estimate. Intervals describe tract distributions, not confidence intervals. Boroughs use the same exact citywide grouping thresholds; labels round those thresholds for readability.
- **04 — Usage comparisons:** two heatmaps show median monthly departures per station and contributing-tract counts. Usage is defined only for tracts with stations. Empty groups stay gray; orange outlines and daggers flag fewer than five tracts as a descriptive caution, without excluding those observations.
- **05 — Demographic associations:** linear axes retain all points, show zero-density tracts above the border, and distinguish income reported as $250,000+. Spearman rho describes rank association; it does not establish causation.
- **06 — Daily departures:** direct labels identify member/casual lines, shaded bands identify weekends, and the annotation compares observed casual daily averages.

`visualizations/figure_data.json` records all plotted group summaries, exact cutpoints, sample sizes, daily means, and display-mask checks. `visualizations/verification.json` reconciles these against tract-level observations and published tables. Each PNG includes a takeaway, units, source dates, and a caption; full population definitions also appear in `captions.json`.

## Organization and submission

`analysis/` contains reusable acquisition, cleaning, spatial, statistical, plotting, report, and verification code. `data/raw/` preserves original inputs; `data/processed/` contains regenerated aggregate tables and the projected tract GeoPackage. `notebooks/` contains the executed notebook; `visualizations/` contains all six PNGs and captions; `docs/` contains the proposal, methods, and editable report text. The report PDF sits at the root as required.

`python -m analysis.package_submission` builds **Group_PAIR_TrackB_midterm.zip**, including raw data and excluding credentials, environments, caches, Git metadata, and the ZIP itself. Files larger than 98 MB are excluded from GitHub. The submission ZIP is a local artifact and is not committed. Upload that ZIP to Gradescope for the group; repository creation does not submit to Gradescope.

The report distinguishes completed midterm work from proposed remaining responsibilities. Computational implementation and report drafting were prepared with AI assistance; the source code, numerical audits, executed notebook, and original inputs are provided for team and instructor review.
