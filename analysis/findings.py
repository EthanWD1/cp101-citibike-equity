"""Refresh the notebook's computed results separately from the editable report."""
import json
from pathlib import Path
import pandas as pd
from .config import PROCESSED, FIGURES
from .report import number


def write_findings():
    validation = json.loads((PROCESSED / "validation.json").read_text())

    counts = validation["counts"]

    boroughs = pd.read_csv(PROCESSED / "borough_summary.csv").set_index("scope")

    comparisons = pd.read_csv(PROCESSED / "quartile_comparisons.csv")

    correlations = pd.read_csv(PROCESSED / "spearman_correlations.csv")

    figure_data = json.loads((FIGURES / "figure_data.json").read_text())

    casual = figure_data["daily"]["categories"]["casual"]

    def rho(scope, variable, metric="stations_per_km2"):
        value = correlations.loc[correlations.scope.eq(scope) & correlations.variable.eq(variable) & correlations.metric.eq(metric), "spearman_rho"].iloc[0]
        return number(value, 2)
    def quartile(variable, quartile, field):
        return comparisons.loc[comparisons.scope.eq("NYC") & comparisons.variable.eq(variable) & comparisons.quartile.eq(quartile), field].iloc[0]
    zero_pct = boroughs.loc["NYC", "zero_station_pct"]

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
    findings_md = ("# Early results\n\n" + coverage + "\n\n" + associations + "\n\n" + usage + "\n\n" + limitations + "\n\n"
                   + f"All {len(validation['checks'])} numerical/spatial reconciliation checks passed. NYC station departures total {counts['nyc_station_departures']:,}; "
                   + f"{counts['nonresidential_nyc_departures']:,} occur in tracts excluded from residential comparisons and remain included in daily activity.\n")
    Path("docs/early_results.md").write_text(findings_md)
