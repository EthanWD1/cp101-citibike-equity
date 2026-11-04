# Submission verification

Visualization revision verified November 3, 2026.

- **14 edge-case tests passed**: the original ten analysis tests plus display-only water subtraction, prevention of eligible-tract loss, empty/small usage groups, and daily calendar denominators with unmatched starts excluded.
- **15 numerical and spatial checks passed**, including trip exclusions, station assignments, eligible denominators, and station/tract/borough/day departure totals.
- **12 figure checks passed**, including all 48 density rows and 48 usage cells, their sample sizes and zero-station percentages, exact cutpoints, scatterplot populations, censored income observations, and daily category means. Staten Island usage stays undefined; Manhattan's two-tract usage group is flagged. See `visualizations/verification.json` and `figure_data.json`.
- **One fresh-kernel execution of the revised notebook succeeded**, using all original raw inputs and the five new water ZIPs. External network connections were blocked in the kernel while localhost communication remained permitted. No download was needed. Data processing took 78.21 seconds on the tested machine, excluding figure/report generation.
- **All 16 analytical CSVs are byte-identical to the previous committed submission.** The stored GeoPackage's original geometries, attributes, CRS, and tract IDs are identical. Analytical counts and exact demographic thresholds are unchanged. Runtime metadata, GeoPackage timestamps, and PDF creation timestamps are not treated as analytical values.
- The display mask preserves all 2,231 eligible tracts, all tract IDs, and all analytical attributes; every resulting geometry is valid. Its density breaks match the previous map. Water subtraction changes only rendering.
- The notebook contains seven executed code cells and no error outputs. Its six embedded PNGs match the standalone figure files byte for byte.
- The PDF is exactly **three pages**; rendered pages and all six figures were visually inspected, and extracted text bounding boxes remain within page margins.
- The GitHub staging list contains no environment, cache, credential file, submission ZIP, or large trip archive; every staged file is below 98 MB.

The original raw inputs and all five water ZIPs are retained in the submission ZIP. The archive is checked for CRC errors when built and includes `SUBMISSION_MANIFEST.json` with per-file SHA-256 hashes. The updated archive's manifest and required deliverables are checked against the final working files before publication.

The prior November 2 submission also passed an independent ZIP extraction and fresh-kernel rerun, with all 22 CSV/PNG files identical and three-page report text unchanged. That historical verification is preserved separately in `verification.json`; it is not counted as a second run of this visualization revision.

Commands to reproduce the analysis checks:

```bash
python -m unittest discover -s tests -v
python -m analysis.execute_notebook
python -m analysis.verify_figures
python -m analysis.package_submission
```

See `verification.json` for counts and measured runtimes, and `data/processed/validation.json` for the individual numerical checks.

## Markdown authoring update — November 4, 2026

The report now compiles directly from `docs/report_source.md`; rebuilding never overwrites that source. All **16 tests passed**, including two new checks that Markdown edits appear in the PDF and that an overlong page preserves both the existing PDF and the user's edits. The compiled report remains three pages; all rendered pages were inspected and text/image bounds stay within the page. The computed notebook summary is unchanged. This was a report-only update, so trip processing and the previously verified notebook execution were not repeated.
