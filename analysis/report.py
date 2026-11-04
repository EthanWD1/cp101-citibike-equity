"""Generate a three-page report and editable Markdown narrative from computed tables."""
import json
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from PIL import Image

from .config import PROCESSED, FIGURES, SCOPES

REPO = "https://github.com/EthanWD1/cp101-citibike-equity"


def number(value, places=1):
    return "N/A" if pd.isna(value) else f"{value:,.{places}f}"


class Report:
    def __init__(self, path):
        self.pdf = canvas.Canvas(str(path), pagesize=letter)
        self.pdf.setTitle("Group PAIR — Citi Bike station density and neighborhood mobility")
        self.pdf.setAuthor("Timothy Phan and Ethan Deng")
        self.width = 536
        self.margin = 38
        self.page = 0
        self.y = 0

    def new_page(self, title):
        if self.page:
            if self.y < 38:
                raise ValueError(f"Report page {self.page} overflowed: y={self.y}")
            self.footer()
            self.pdf.showPage()
        self.page += 1
        self.y = 752
        self.pdf.setFillColor(colors.HexColor("#214c64"))
        self.pdf.setFont("Helvetica-Bold", 17)
        self.pdf.drawString(self.margin, self.y, title)
        self.y -= 21
        self.pdf.setStrokeColor(colors.HexColor("#b9c8cf"))
        self.pdf.line(self.margin, self.y + 8, self.margin + self.width, self.y + 8)

    def para(self, text, size=9.5, leading=12.4, gap=7, bold=False):
        style = ParagraphStyle("body", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                               leading=leading, textColor=colors.HexColor("#202b30"))
        paragraph = Paragraph(text, style)
        _, height = paragraph.wrap(self.width, 1000)
        paragraph.drawOn(self.pdf, self.margin, self.y - height)
        self.y -= height + gap

    def table(self, rows, widths, font=8.2):
        style = ParagraphStyle("table", fontName="Helvetica", fontSize=font, leading=font+2)
        content = [[Paragraph(escape(str(cell)), style) for cell in row] for row in rows]
        table = Table(content, colWidths=widths, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e5edf1")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LINEBELOW", (0,0), (-1,0), .6, colors.HexColor("#a6b9c5")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f7f8")]),
        ]))
        _, height = table.wrap(self.width, 1000)
        table.drawOn(self.pdf, self.margin, self.y-height)
        self.y -= height + 8

    def picture(self, filename, width):
        with Image.open(FIGURES / filename) as img:
            height = width * img.height / img.width
        self.pdf.drawImage(str(FIGURES / filename), self.margin + (self.width-width)/2,
                           self.y-height, width=width, height=height, preserveAspectRatio=True)
        self.y -= height + 5

    def footer(self):
        self.pdf.setFont("Helvetica", 8)
        self.pdf.setFillColor(colors.HexColor("#58646a"))
        self.pdf.drawString(self.margin, 23, "Group PAIR · CYPLAN 101 · Track B · Revised November 3, 2026")
        self.pdf.drawRightString(574, 23, f"{self.page} / 3")

    def finish(self):
        if self.y < 38 or self.page != 3:
            raise ValueError(f"Expected three unclipped pages, got {self.page}, y={self.y}")
        self.footer()
        self.pdf.save()


def build_report():
    validation = json.loads((PROCESSED / "validation.json").read_text())
    counts = validation["counts"]
    boroughs = pd.read_csv(PROCESSED / "borough_summary.csv").set_index("scope")
    comparisons = pd.read_csv(PROCESSED / "quartile_comparisons.csv")
    correlations = pd.read_csv(PROCESSED / "spearman_correlations.csv")
    ledger = pd.read_csv(PROCESSED / "cleaning_ledger.csv")
    missingness = pd.read_csv(PROCESSED / "missingness_by_date_category.csv")
    tracts = pd.read_csv(PROCESSED / "tract_metrics.csv")
    figure_data = json.loads((FIGURES / "figure_data.json").read_text())
    casual = figure_data["daily"]["categories"]["casual"]
    def rho(scope, variable, metric="stations_per_km2"):
        value = correlations.loc[correlations.scope.eq(scope) & correlations.variable.eq(variable) & correlations.metric.eq(metric), "spearman_rho"].iloc[0]
        return number(value, 2)
    def quartile(variable, quartile, field):
        return comparisons.loc[comparisons.scope.eq("NYC") & comparisons.variable.eq(variable) & comparisons.quartile.eq(quartile), field].iloc[0]
    missing_income = int((tracts.eligible & tracts.income.isna()).sum())
    zero_pct = boroughs.loc["NYC", "zero_station_pct"]
    question = ("How did observed Citi Bike station density and usage vary with median household income and the share of households without a vehicle "
                "across New York City census tracts in September 2025, citywide and within each borough? "
                "The geography, month, demographic variables, and descriptive approach remain as proposed. The audience is NYC transportation planners "
                "and community groups assessing where observed coverage merits closer review.")
    status = ("Completed: full-month acquisition, documented cleaning, point-to-tract spatial join, citywide/borough comparisons, one map and five charts, "
              "and a reproducible Python workflow. Static figures are the midterm milestone. Animated maps, the webpage, and operational/boundary "
              "sensitivity checks remain final-project work; no historical station inventory has been replaced by a current feed.")
    data_text = (f"All six original trip CSVs contain {counts['raw_rows']:,} rows. ACS 2020–2024 five-year tables B19013 (income), B08201 "
                 "(households/vehicle availability), and B01003 (population) supply tract context; 2024 TIGER/Line supplies boundaries and land area. "
                 "ACS data were obtained from official table-based text files without an API key. Raw files, download dates, URLs, and SHA-256 checksums are retained.")
    cleaning = (f"The sequential trip filters remove {counts['outside_september']:,} starts outside September; missing ride IDs, duplicate IDs, "
                f"and invalid start timestamps each affect {counts['missing_ride_id']:,}, {counts['duplicate_ride_id']:,}, and {counts['invalid_start_time']:,} rows, respectively. "
                f"Of {counts['retained_september']:,} retained starts, {counts['missing_id_and_coordinates']:,} lack both a start station ID and usable coordinates "
                f"and cannot enter station usage. Missing destination IDs affect {int(missingness.missing_end_id.sum()):,} retained trips but do not remove their valid departures.")
    geography = (f"The spatial join assigns {counts['observed_nyc_stations']:,} of {counts['observed_station_ids_with_coordinates']:,} located station IDs to NYC; "
                 f"{counts['unmatched_station_locations']:,} station locations outside/unmatched to NYC remain audited. There are {counts['boundary_tie_stations']:,} boundary ties. "
                 f"Residential comparisons retain {counts['eligible_tracts']:,} of {counts['all_nyc_tracts']:,} NYC tracts; {counts['all_nyc_tracts']-counts['eligible_tracts']:,} fail the positive-household/population/land-area rule. "
                 f"Another {missing_income:,} eligible tracts lack income and remain mapped but are excluded only from income comparisons. "
                 f"The {counts['income_censored_eligible']:,} upper-bound income estimates are flagged; {counts['income_imprecise_eligible']:,} eligible tracts have income MOEs above half their estimate.")
    methods = ("1. Parse local timestamps, keep September starts, and deduplicate ride IDs across files using a disk-backed index. "
               "2. Infer station locations from both endpoints by modal coordinate pair, preserving string IDs. "
               "3. Project to <b>EPSG:32618 (meters)</b>, spatially intersect stations with tracts, and merge ACS by eleven-digit GEOID. "
               "4. Aggregate starts by their station's tract; calculate stations/land km², stations/10,000 residents, and departures/observed station. "
               "5. Compare unweighted tracts using fixed citywide income and no-vehicle-share quartiles within every borough; report descriptive Spearman correlations. "
               "Coverage includes zeros; usage excludes zero-station tracts. Land area is TIGER ALAND/1,000,000, excluding water from the denominator.")
    coverage = (f"Observed coverage is uneven: {counts['zero_station_eligible_tracts']:,} of {counts['eligible_tracts']:,} eligible tracts ({zero_pct:.1f}%) have no observed station. "
                f"The share is {boroughs.loc['Manhattan','zero_station_pct']:.1f}% in Manhattan, {boroughs.loc['Queens','zero_station_pct']:.1f}% in Queens, and 100% in Staten Island. "
                "These are observations from trip records, not a claim that residents cannot reach stations in adjacent tracts.")
    associations = (f"The citywide income–density correlation is nearly flat (ρ={rho('NYC','income')}), but borough patterns differ: "
                    f"Bronx {rho('Bronx','income')}, Brooklyn {rho('Brooklyn','income')}, Manhattan {rho('Manhattan','income')}, and Queens {rho('Queens','income')}. "
                    f"No-vehicle household share is more positively associated with density citywide (ρ={rho('NYC','no_vehicle_share')}). "
                    f"Its highest quartile has {quartile('no_vehicle_share','Q4','zero_station_pct'):.1f}% zero-station tracts, versus "
                    f"{quartile('no_vehicle_share','Q1','zero_station_pct'):.1f}% in its lowest quartile. The borough differences caution against a single citywide income story.")
    usage = (f"Among tracts with stations, median September departures per observed station rise from "
             f"{quartile('income','Q1','departures_per_station_median'):,.0f} in the lowest income quartile to "
             f"{quartile('income','Q4','departures_per_station_median'):,.0f} in the highest. This conditional comparison describes activity where stations were observed, "
             f"not demand in unserved tracts or trips made by residents. Casual departures averaged {casual['weekend_daily_mean']:,.0f}/day on weekends "
             f"versus {casual['weekday_daily_mean']:,.0f} on weekdays this month; no causal explanation is established.")
    limitations = ("ACS estimates cover five years and have sampling uncertainty; they do not describe individual riders. Tract boundaries, jobs, transit, "
                   "land use, and partial-month operation can affect the patterns. The one flagged station location spans 291 m; its modal pair accounts for "
                   "383 of 389 endpoint observations, and both locations fall in the same tract. We retain the modal location with no manual override. "
                   "Low observed density is not a direct walking-access measure, and low usage does not establish low or unmet demand.")
    plan = ("<b>Ethan · Nov 16:</b> review land/population normalization and boundary effects; repeat usage comparisons for stations observed in both first and last weeks. "
            "<b>Tim · Dec 6:</b> build the two interactive maps, daily animations, fixed scales, borough filters, and GitHub Pages draft. "
            "<b>Both · Dec 15:</b> review interpretation, rerun the workflow, and finalize. Main risks are uncertain exposure, ACS precision, and map performance; "
            "use sensitivity checks and aggregated layers rather than adding causal claims or rendering individual trips.")
    feedback = ("Feedback requested: (1) How should nearby stations across tract boundaries be represented? "
                "(2) Are these descriptive comparisons sufficient given ACS uncertainty and correlated land use? "
                "(3) Is first/last-week station presence a useful check for partial-month exposure?")
    findings_md = ("# Early results\n\n" + coverage + "\n\n" + associations + "\n\n" + usage + "\n\n" + limitations + "\n\n"
                   + f"All {len(validation['checks'])} numerical/spatial reconciliation checks passed. NYC station departures total {counts['nyc_station_departures']:,}; "
                   + f"{counts['nonresidential_nyc_departures']:,} occur in tracts excluded from residential comparisons and remain included in daily activity.\n")
    Path("docs/early_results.md").write_text(findings_md)
    source = ["# Group PAIR midterm report", "Timothy Phan and Ethan Deng · Revised November 3, 2026 · Track B", "", "## Research question and status", question, "", status,
              "", "## Data and cleaning", data_text, "", cleaning, "", geography, "", "## Methods", methods.replace("<b>", "").replace("</b>", ""),
              "", "## Early results", coverage, "", associations, "", usage, "", "## Limitations", limitations, "", "## Plan to finish", plan.replace("<b>", "").replace("</b>", ""),
              "", feedback, "", "## Reproducibility and figures", f"Repository: {REPO}",
              "The report embeds figures 01 and 06; figures 02–05 and complete comparison tables accompany the PDF. All six figures have titles, units, sources, and captions.",
              "Figure 01 subtracts 2024 Census Area Hydrography only from display geometry; original tracts, spatial joins, and TIGER ALAND denominators are unchanged. Figures 02–03 show medians, middle-50% intervals, zero-station percentages, and tract counts on a linear density scale. Figure 04 shows usage medians and contributing-tract counts, flags n<5, and distinguishes undefined usage. Figure 05 retains all observations and flags censored income. Figure 06 shades weekends and labels rider categories directly.",
              "Official source links and data-use terms are listed in README.md and data/raw/sources.json."]
    Path("docs/report_source.md").write_text("\n\n".join(source) + "\n")
    report = Report("Group_PAIR_midterm.pdf")
    report.new_page("Citi Bike coverage and neighborhood mobility")
    report.para("<b>Timothy Phan and Ethan Deng · Group PAIR · Midterm progress report</b>", size=9.5)
    report.para("Research question and current state", size=11, bold=True, gap=4)
    report.para(question)
    report.para(status)
    report.para("Data and documented cleaning", size=11, bold=True, gap=4)
    report.para(data_text)
    report.para(cleaning)
    rows = [["Stage", "Before", "Affected / excluded", "After"]]
    for key, label in [("missing_ride_id", "Missing ride ID"), ("duplicate_ride_id", "Duplicate ride ID"),
                       ("invalid_start_time", "Invalid start timestamp"), ("outside_september", "Start outside September")]:
        row = ledger.loc[ledger.stage.eq("trips") & ledger.step.eq(key)].iloc[0]
        rows.append([label, f"{row.before:,}", f"{row.affected:,}", f"{row.after:,}"])
    rows.append(["Eligible residential tracts", f"{counts['all_nyc_tracts']:,}", f"{counts['all_nyc_tracts']-counts['eligible_tracts']:,}", f"{counts['eligible_tracts']:,}"])
    report.table(rows, [212, 96, 132, 96], font=8.2)
    report.para(geography, size=9, leading=11.6)
    report.para("Methods and validation", size=11, bold=True, gap=4)
    report.para(methods, size=9, leading=11.6)
    report.para(f"All {len(validation['checks'])} reconciliation checks pass. The {counts['nyc_station_departures']:,} assigned NYC departures reconcile across stations, tracts, boroughs, and dates; "
                f"{counts['nonresidential_nyc_departures']:,} are in ineligible residential-comparison tracts. The notebook regenerates outputs from raw inputs using relative paths.", size=8.8, leading=11.2)
    report.new_page("Early results: coverage across all five boroughs")
    report.para(coverage, size=10, leading=13)
    report.picture("01_station_density_map.png", width=490)
    rows = [["Borough", "Eligible tracts", "Zero stations (%)", "Median stations / km²", "Sept. departures*"]]
    for scope in SCOPES[1:]:
        row = boroughs.loc[scope]
        rows.append([scope, f"{int(row.eligible_tracts):,}", number(row.zero_station_pct), number(row.median_stations_per_km2,2), f"{int(row.departures_all_tracts):,}"])
    report.table(rows, [102, 83, 111, 124, 116], font=8.1)
    report.para("*Departures include all assigned NYC stations, including tracts outside the residential comparison. Density medians and zero percentages use eligible tracts only. Figure 01 removes 2024 Census water polygons for display; original tracts, station assignments, and ALAND denominators remain unchanged. Full-size PNGs accompany this report.", size=8, leading=10.2)
    report.new_page("Early results, limitations, and plan to finish")
    report.para(associations, size=9.4, leading=12.2)
    report.para(usage, size=9.4, leading=12.2)
    report.picture("06_daily_departures.png", width=510)
    report.para("Interpretation and remaining risks", size=10.5, bold=True, gap=4)
    report.para(limitations, size=9, leading=11.6)
    report.para("Plan to finish and requested feedback", size=10.5, bold=True, gap=4)
    report.para(plan, size=9, leading=11.6)
    report.para(feedback, size=8.8, leading=11.2)
    report.para("Companion figures: 02–03 density medians and middle-50% intervals with zero-station shares and n; 04 usage heatmaps with n (groups below 5 flagged); "
                "05 linear scatterplots with censored incomes marked. Full citywide/borough tables accompany the notebook.", size=8, leading=10.2)
    report.para(f'<b>Sources and code:</b> <link href="https://citibikenyc.com/system-data" color="#214c64">Citi Bike trip histories</link>; '
                '<link href="https://www.census.gov/programs-surveys/acs/data/summary-file.2024.html" color="#214c64">ACS 2024 five-year Summary File</link>; '
                '<link href="https://www2.census.gov/geo/tiger/TIGER2024/TRACT/tl_2024_36_tract.zip" color="#214c64">TIGER/Line 2024 tracts</link>; '
                '<link href="https://www2.census.gov/geo/tiger/TIGER2024/AREAWATER/" color="#214c64">water polygons</link>. '
                f'<link href="{REPO}" color="#214c64">github.com/EthanWD1/cp101-citibike-equity</link>. Full provenance, attribution, and computational-assistance notes are in the README.', size=7.7, leading=10)
    report.finish()
    print("Generated three-page report and Markdown sources.", flush=True)


if __name__ == "__main__":
    build_report()
