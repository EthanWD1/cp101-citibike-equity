# Submission verification

Verified November 2, 2026.

- **10 edge-case tests passed**, covering global duplicates, missing destinations, out-of-period starts, string IDs, coordinate-only starts, coordinate bounds, station modal ties, tract boundaries, ACS sentinels, tied quartiles, and zero-coverage/empty groups.
- **15 numerical and spatial checks passed**, including trip exclusions, station assignments, eligible denominators, and station/tract/borough/day departure totals.
- **Two fresh-kernel notebook executions succeeded**: one in the project and one after extracting the submission ZIP into a separate directory. Both used the project's Python environment and blocked external network connections in the kernel while allowing localhost communication. No source download was needed.
- Every packaged file was checked against its SHA-256 manifest before the extracted copy was run. All regenerated CSV tables and PNG figures matched the original files byte for byte; report text matched across all three pages. Runtime metadata and PDF creation timestamps are not compared as analytical outputs.
- The notebook contains seven executed code cells and no error outputs.
- The PDF is exactly **three pages**; rendered pages and all six figures were visually inspected, and extracted text bounding boxes remain within page margins.
- The GitHub staging list contains no environment, cache, credential file, submission ZIP, or large trip archive; every staged file is below 98 MB.

The original raw inputs are retained in the submission ZIP. The archive is checked for CRC errors when built and includes `SUBMISSION_MANIFEST.json` with per-file SHA-256 hashes.

Commands to reproduce the analysis checks:

```bash
python -m unittest discover -s tests -v
python -m analysis.execute_notebook
python -m analysis.package_submission
```

See `verification.json` for counts and measured runtimes, and `data/processed/validation.json` for the individual numerical checks.
