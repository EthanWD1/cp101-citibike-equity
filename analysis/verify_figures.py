"""Reconcile rendered summaries against tract observations and published tables."""
import json

import geopandas as gpd
import numpy as np
import pandas as pd

from .config import PROCESSED, FIGURES


def verify():
    data = json.loads((FIGURES / "figure_data.json").read_text())
    captions = json.loads((FIGURES / "captions.json").read_text())
    tracts = gpd.read_file(PROCESSED / "tract_metrics.gpkg")
    comparisons = pd.read_csv(PROCESSED / "quartile_comparisons.csv")
    validation = json.loads((PROCESSED / "validation.json").read_text())
    eligible = tracts.loc[tracts.eligible]
    checks = {}

    def equal(actual, expected):
        if expected is None or pd.isna(expected):
            return actual is None
        return actual is not None and bool(np.isclose(actual, expected, rtol=1e-8, atol=1e-8))

    checks["map_population_and_zero_share"] = (
        data["map"]["eligible_tracts"] == len(eligible)
        and data["map"]["zero_station_tracts"] == int(eligible.observed_stations.eq(0).sum())
        and equal(data["map"]["zero_station_pct"], 100*eligible.observed_stations.eq(0).mean()))
    checks["display_geometry_valid_without_eligible_loss"] = (
        data["map"]["valid_display_geometries"] and data["map"]["eligible_display_geometries_lost"] == 0)
    checks["display_ids_and_attributes_unchanged"] = (
        data["map"]["tract_ids_preserved"] and data["map"]["analytical_attributes_preserved"])
    positive = eligible.loc[eligible.observed_stations.gt(0), "stations_per_km2"]
    checks["map_density_breaks"] = bool(np.allclose(captions["positive_density_breaks"], positive.quantile([.25,.5,.75])))
    checks["exact_citywide_cutoffs"] = all(np.allclose(values,validation["quartile_thresholds"][variable],rtol=1e-12)
                                           for variable,values in data["exact_group_thresholds"].items())
    density_ok, usage_ok = [], []
    for record in data["density_groups"]:
        variable, scope, quartile = [record[key] for key in ["variable","scope","quartile"]]
        group_field = "income_quartile" if variable == "income" else "no_vehicle_quartile"
        group = eligible.loc[eligible[group_field].eq(quartile)]
        if scope != "NYC":
            group = group.loc[group.borough.eq(scope)]
        table = comparisons.loc[comparisons.scope.eq(scope) & comparisons.variable.eq(variable) & comparisons.quartile.eq(quartile)].iloc[0]
        matches = record["tracts"] == len(group) == int(table.tracts)
        matches &= equal(record["zero_station_pct"],100*group.observed_stations.eq(0).mean())
        matches &= equal(record["zero_station_pct"],table.zero_station_pct)
        for field, q in [("p25",.25),("median",.5),("p75",.75)]:
            matches &= equal(record[field],group.stations_per_km2.quantile(q))
            matches &= equal(record[field],table[f"stations_per_km2_{field}"])
        density_ok.append(matches)
    for record in data["usage_groups"]:
        variable, scope, quartile = [record[key] for key in ["variable","scope","quartile"]]
        field = "income_quartile" if variable == "income" else "no_vehicle_quartile"
        group = eligible.loc[eligible[field].eq(quartile) & eligible.observed_stations.gt(0)]
        if scope != "NYC":
            group = group.loc[group.borough.eq(scope)]
        table = comparisons.loc[comparisons.scope.eq(scope) & comparisons.variable.eq(variable) & comparisons.quartile.eq(quartile)].iloc[0]
        usage_ok.append(record["served_tracts"] == len(group) == int(table.served_tracts)
                        and equal(record["median"],group.departures_per_station.median())
                        and equal(record["median"],table.departures_per_station_median)
                        and record["small_group"] == (0 < len(group) < 5))
    checks["all_48_density_groups_match_tracts_and_tables"] = len(density_ok) == 48 and all(density_ok)
    checks["all_48_usage_groups_match_tracts_and_tables"] = len(usage_ok) == 48 and all(usage_ok)
    checks["staten_island_usage_undefined"] = all(r["median"] is None and r["served_tracts"] == 0
                                                for r in data["usage_groups"] if r["scope"] == "Staten Island")
    small_manhattan = next(r for r in data["usage_groups"] if (r["scope"],r["variable"],r["quartile"]) == ("Manhattan","no_vehicle_share","Q2"))
    checks["manhattan_two_tract_group_flagged"] = small_manhattan["served_tracts"] == 2 and small_manhattan["small_group"]
    scatter_ok = []
    for record in data["scatter_panels"]:
        group = eligible.dropna(subset=[record["variable"],record["metric"]])
        density = record["metric"] == "stations_per_km2"
        scatter_ok.append(record["plotted_tracts"] == record["correlation_tracts"] == len(group)
                          and record["all_values_in_range"]
                          and record["zero_station_tracts"] == (int(group.observed_stations.eq(0).sum()) if density else 0)
                          and record["censored_income_tracts"] == (int(group.income_censored.sum()) if record["variable"] == "income" else 0))
    checks["all_scatter_observations_zeros_and_censored_incomes_retained"] = len(scatter_ok) == 4 and all(scatter_ok)
    daily = pd.read_csv(PROCESSED / "station_daily_departures.csv",dtype={"GEOID":str})
    daily = daily.loc[daily.GEOID.notna()].copy()
    daily["weekend"] = pd.to_datetime(daily.date).dt.day_of_week >= 5
    summary = data["daily"]
    checks["daily_calendar_and_departure_totals"] = (summary["weekend_days"] == 8 and summary["weekday_days"] == 22
        and sum(r["departures"] for r in summary["categories"].values()) == int(daily.departures.sum()) == validation["counts"]["nyc_station_departures"])
    checks["daily_category_means"] = all(
        equal(record["weekend_daily_mean"],daily.loc[daily.member_casual.eq(category) & daily.weekend,"departures"].sum()/8)
        and equal(record["weekday_daily_mean"],daily.loc[daily.member_casual.eq(category) & ~daily.weekend,"departures"].sum()/22)
        for category,record in summary["categories"].items())
    checks = {key:bool(value) for key,value in checks.items()}
    if not all(checks.values()):
        raise AssertionError({key:value for key,value in checks.items() if not value})
    (FIGURES / "verification.json").write_text(json.dumps(checks,indent=2)+"\n")
    print(f"Passed {len(checks)} figure checks, including all 96 demographic group summaries.")
    return checks


if __name__ == "__main__":
    verify()
