"""Tract-level rates, fixed citywide quartiles, and descriptive comparisons."""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .config import GROUPS, SCOPES

METRICS = ["stations_per_km2", "stations_per_10000", "departures_per_station"]
GROUPING = {"income": "income_quartile", "no_vehicle_share": "no_vehicle_quartile"}


def assign_quartiles(values, thresholds):
    """Equal values stay together: Q1 <= p25, Q2 <= p50, Q3 <= p75, Q4 > p75."""
    result = pd.Series(pd.NA, index=values.index, dtype="string")
    valid = values.notna()
    if len(thresholds) == 3:
        result.loc[valid] = [GROUPS[i] for i in np.searchsorted(thresholds, values[valid], side="left")]
    return result


def calculate_metrics(tracts, stations, station_daily, ledger):
    lookup = stations[["station_id", "GEOID", "borough"]]
    daily = station_daily.merge(lookup, on="station_id", how="left", validate="many_to_one")
    observed = stations.dropna(subset=["GEOID"])
    assigned = daily.dropna(subset=["GEOID"])
    tracts = tracts.copy()
    tracts["observed_stations"] = tracts.GEOID.map(observed.groupby("GEOID").station_id.nunique()).fillna(0).astype(int)
    tracts["departures"] = tracts.GEOID.map(assigned.groupby("GEOID").departures.sum()).fillna(0).astype(int)
    tracts["stations_per_km2"] = tracts.observed_stations / tracts.land_km2.where(tracts.land_km2.gt(0))
    tracts["stations_per_10000"] = 10000 * tracts.observed_stations / tracts.population.where(tracts.population.gt(0))
    tracts["departures_per_station"] = tracts.departures / tracts.observed_stations.where(tracts.observed_stations.gt(0))
    thresholds = {}
    for variable, group in GROUPING.items():
        values = tracts.loc[tracts.eligible, variable].dropna()
        cuts = values.quantile([.25, .50, .75]).tolist() if len(values) else []
        thresholds[variable] = cuts
        tracts[group] = assign_quartiles(tracts[variable].where(tracts.eligible), cuts)
        ledger.append(dict(stage="demographic_comparison", step=f"missing_{variable}", before=int(tracts.eligible.sum()),
                           affected=int((tracts.eligible & tracts[variable].isna()).sum()),
                           after=int((tracts.eligible & tracts[variable].notna()).sum()), action="exclude_from_comparison",
                           reason="Unavailable grouping variable; retain tract for map and other comparisons"))
    comparisons, correlations, boroughs = [], [], []
    for scope in SCOPES:
        all_area = tracts if scope == "NYC" else tracts.loc[tracts.borough.eq(scope)]
        area = all_area.loc[all_area.eligible]
        served = area.loc[area.observed_stations.gt(0)]
        boroughs.append({"scope": scope, "all_tracts": len(all_area), "eligible_tracts": len(area),
                        "zero_station_tracts": int(area.observed_stations.eq(0).sum()),
                        "zero_station_pct": 100 * area.observed_stations.eq(0).mean() if len(area) else np.nan,
                        "observed_stations_all_tracts": int(all_area.observed_stations.sum()),
                        "observed_stations_eligible": int(area.observed_stations.sum()),
                        "departures_all_tracts": int(all_area.departures.sum()),
                        "departures_eligible": int(area.departures.sum()),
                        "median_stations_per_km2": area.stations_per_km2.median(),
                        "median_stations_per_10000": area.stations_per_10000.median(),
                        "median_departures_per_station": served.departures_per_station.median()})
        for variable, group in GROUPING.items():
            for quartile in GROUPS:
                subset = area.loc[area[group].eq(quartile)]
                served_subset = subset.loc[subset.observed_stations.gt(0)]
                row = {"scope": scope, "variable": variable, "quartile": quartile,
                       "tracts": len(subset), "served_tracts": len(served_subset),
                       "zero_station_pct": 100 * subset.observed_stations.eq(0).mean() if len(subset) else np.nan,
                       "status": "ok" if len(subset) else "empty group"}
                for metric in METRICS:
                    values = (served_subset if metric == "departures_per_station" else subset)[metric].dropna()
                    row.update({f"{metric}_{stat}": value for stat, value in [
                        ("median", values.median()), ("p25", values.quantile(.25)), ("p75", values.quantile(.75)),
                        ("min", values.min()), ("max", values.max())]})
                comparisons.append(row)
            for metric in METRICS:
                pairs = area[[variable, metric]].dropna()
                valid = len(pairs) >= 3 and pairs[variable].nunique() > 1 and pairs[metric].nunique() > 1
                correlations.append({"scope": scope, "variable": variable, "metric": metric, "tracts": len(pairs),
                                     "spearman_rho": float(spearmanr(pairs[variable], pairs[metric]).statistic) if valid else np.nan,
                                     "status": "descriptive" if valid else "not applicable: insufficient or constant values"})
    return tracts, daily, thresholds, pd.DataFrame(comparisons), pd.DataFrame(correlations), pd.DataFrame(boroughs)


def validate_results(trips, tracts, stations, daily, coordinate_only):
    totals = trips["totals"]
    missing = trips["missingness"]
    mapped = daily.loc[daily.GEOID.notna()]
    num_nyc = int(mapped.departures.sum())
    num_unmapped = int(daily.loc[daily.GEOID.isna(), "departures"].sum())
    with_id = int(daily.departures.sum())
    missing_id = int(missing.missing_start_id.sum())
    coordinate_count = int(coordinate_only.departures.sum())
    checks = {
        "six_files_processed": len(trips["files"]) == 6,
        "sequential_exclusions_reconcile": totals["raw_rows"] == totals["retained_september"] + sum(totals[k] for k in ["missing_ride_id", "duplicate_ride_id", "invalid_start_time", "outside_september"]),
        "retained_start_ids_reconcile": totals["retained_september"] == with_id + missing_id,
        "retained_missingness_reconciles": totals["retained_september"] == int(missing.retained_starts.sum()),
        "one_station_row_per_id": stations.station_id.is_unique,
        "one_row_per_tract": tracts.GEOID.is_unique,
        "all_geoid_lengths": bool(tracts.GEOID.str.fullmatch(r"\d{11}").all()),
        "station_tract_totals_reconcile": int(tracts.observed_stations.sum()) == int(stations.GEOID.notna().sum()),
        "nyc_departures_reconcile": int(tracts.departures.sum()) == num_nyc,
        "nyc_borough_departures_reconcile": int(mapped.groupby("borough").departures.sum().sum()) == num_nyc,
        "nyc_daily_departures_reconcile": int(mapped.groupby("date").departures.sum().sum()) == num_nyc,
        "zero_station_usage_is_missing": bool(tracts.loc[tracts.observed_stations.eq(0), "departures_per_station"].isna().all()),
        "zero_station_departures_are_zero": bool(tracts.loc[tracts.observed_stations.eq(0), "departures"].eq(0).all()),
        "household_numerators_valid": bool(tracts.no_vehicle_households.dropna().ge(0).all() and tracts.no_vehicle_share.dropna().between(0, 1).all()),
        "positive_residential_denominators": bool(tracts.loc[tracts.eligible, ["households", "population", "land_km2"]].gt(0).all().all()),
    }
    assert all(checks.values()), {k: v for k, v in checks.items() if not v}
    return {"checks": {k: bool(v) for k,v in checks.items()}, "counts": {
        **totals, "station_identified_starts": with_id, "unassigned_station_identified_starts": num_unmapped,
        "nyc_station_departures": num_nyc, "coordinate_only_starts": coordinate_count,
        "coordinate_only_nyc_starts": int(coordinate_only.loc[coordinate_only.GEOID.notna(), "departures"].sum()),
        "missing_id_and_coordinates": missing_id - coordinate_count,
        "observed_station_ids_with_coordinates": len(stations), "observed_nyc_stations": int(stations.GEOID.notna().sum()),
        "unmatched_station_locations": int(stations.GEOID.isna().sum()),
        "boundary_tie_stations": int(stations.tract_matches.gt(1).sum()),
        "location_review_flags": int(stations.location_review_flag.sum()),
        "all_nyc_tracts": len(tracts), "eligible_tracts": int(tracts.eligible.sum()),
        "zero_station_eligible_tracts": int((tracts.eligible & tracts.observed_stations.eq(0)).sum()),
        "nonresidential_nyc_departures": int(tracts.loc[~tracts.eligible, "departures"].sum()),
        "income_censored_eligible": int((tracts.eligible & tracts.income_censored).sum()),
        "income_imprecise_eligible": int((tracts.eligible & tracts.income_imprecise).sum()),
    }}
