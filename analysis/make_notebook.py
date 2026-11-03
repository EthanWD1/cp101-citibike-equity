"""Build the readable notebook; use execute_notebook to run it from a fresh kernel."""
from pathlib import Path
import nbformat as nbf


def build():
    md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
    cells = [
        md("# Citi Bike station density and neighborhood mobility\n**Timothy Phan and Ethan Deng · Group PAIR · CYPLAN 101, Track B · November 2, 2026**\n\n"
           "How did observed station density and usage vary with income and the share of households without a vehicle across NYC tracts in September 2025, citywide and within each borough?\n\n"
           "This notebook rebuilds the complete analysis from the six trip CSVs in the original archive, ACS 2020–2024, and TIGER/Line 2024. The download step is separate; the submission ZIP includes all inputs. Run **Kernel → Restart & Run All** with the project environment. No sampling is used."),
        code("from pathlib import Path\nimport os, sys\nif not Path('analysis').is_dir():\n    if Path('../analysis').is_dir():\n        os.chdir('..')\n    else:\n        raise RuntimeError('Open this notebook from the project root or notebooks folder')\nsys.path.insert(0, '.')\nos.environ.setdefault('MPLCONFIGDIR', '.cache/matplotlib')\nif os.environ.get('CP101_OFFLINE') == '1':\n    from analysis.offline import block_external_network\n    block_external_network()\n    print('Verification mode: external network disabled; local kernel communication allowed.')\nimport json\nimport pandas as pd\nfrom IPython.display import display, Image, Markdown"),
        md("## Sources and reproducible workflow\nThe source manifest records official URLs, UTC download times, byte sizes, and SHA-256 checksums. Raw inputs are never edited.\n\n"
           "The pipeline deduplicates rides globally, retains September starts, infers observed station locations from both endpoints, projects to **EPSG:32618**, spatially joins points to tracts, merges ACS by GEOID, and computes tract and borough comparisons. Repeated operations live in reusable functions under `analysis/`."),
        code("sources = json.loads(Path('data/raw/sources.json').read_text())\ndisplay(pd.DataFrame(sources).T)"),
        code("from analysis.pipeline import run\nvalidation = run()\nassert all(validation['checks'].values())"),
        md("## Cleaning and missingness\nThe ledger gives before/affected/after counts and justifications. Trip exclusions are sequential; endpoint and demographic flags refer to different populations and must not be added to trip removals. A missing destination does not remove a valid departure.\n\nStation IDs remain strings. Coordinate-only starts are counted separately and never generate inferred stations. Modal locations combine both endpoints; exact coordinate ties use latitude then longitude. Locations spanning over 100 m are flagged for inspection, without silent overrides."),
        code("display(pd.read_csv('data/processed/trip_file_audit.csv'))\ndisplay(pd.read_csv('data/processed/cleaning_ledger.csv'))\nmissingness = pd.read_csv('data/processed/missingness_by_date_category.csv')\ndisplay(missingness.groupby('member_casual').sum(numeric_only=True))\ndisplay(pd.read_csv('data/processed/station_location_flags.csv', dtype={'station_id': str, 'GEOID': str}))"),
        md("## Measures and comparison populations\nCoverage includes every eligible residential tract, including zeros. Eligibility requires positive households, population, and land area. Density is observed stations divided by TIGER land area in km²; the alternative normalization is stations per 10,000 ACS residents. Usage is September departures divided by observed stations, defined only in tracts with stations.\n\n"
           "Income and no-vehicle-share quartiles use citywide thresholds held constant within boroughs. Equal values stay together; empty groups remain labeled. ACS bound estimates are flagged and placed at their category boundary; unavailable values remain missing. Comparisons are unweighted across tracts. Spearman correlations are descriptive, without causal or significance claims."),
        code("display(pd.DataFrame(validation['quartile_thresholds'], index=['25th percentile','50th percentile','75th percentile']))\ndisplay(pd.read_csv('data/processed/borough_summary.csv'))\ndisplay(pd.read_csv('data/processed/quartile_comparisons.csv'))\ndisplay(pd.read_csv('data/processed/spearman_correlations.csv'))"),
        md("## One map and five charts\nEvery figure includes units, sources, and a caption. Full-resolution copies are in `visualizations/`. The report embeds selected figures and discusses the accompanying comparison tables."),
        code("figures = json.loads(Path('visualizations/captions.json').read_text())['figures']\nfor figure in figures:\n    display(Image(filename=str(Path('visualizations') / figure['file']), width=1000))\n    display(Markdown(figure['caption']))"),
        md("## Early interpretation and remaining work\nThe report narrative below is generated from the same summary tables as the figures. It describes observed coverage and activity, not dock capacity, reliable availability, rider residence, or causal effects. A tract can have no observed station yet be close to a station across its boundary."),
        code("display(Markdown(Path('docs/early_results.md').read_text()))\ndisplay(pd.Series(validation['checks'], name='passed'))"),
        md("## Plan to finish\n- **Ethan, November 16:** review coordinate flags and tract-boundary sensitivity; compare land/population normalization and usage among stations observed in both first and last weeks.\n- **Tim, December 6:** build the two interactive maps, daily animation, borough filters, and GitHub Pages draft with fixed scales.\n- **Both, December 15:** review interpretations, rerun all code, and finalize.\n\n"
           "Feedback requested: How should near-boundary stations be represented without overstating walking access? Are these descriptive tract comparisons sufficient given ACS uncertainty and correlated land use? Is first/last-week presence a useful sensitivity check for partial-month exposure?"),
    ]
    for index, cell in enumerate(cells):
        cell.id = f"pair-{index:02d}"
    notebook = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"display_name":"Python 3 (project environment)", "language":"python", "name":"python3"}, "language_info":{"name":"python","version":"3.13.12"}})
    Path("notebooks").mkdir(exist_ok=True)
    nbf.write(notebook, "notebooks/midterm_analysis.ipynb")


if __name__ == "__main__":
    build()
