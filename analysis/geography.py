"""Tract demographics, observed station locations, and spatial assignments."""
import numpy as np
import pandas as pd
import geopandas as gpd

from .config import RAW, COUNTIES, CRS

ACS_FIELDS = {
    "b19013": {"001": "income"},
    "b08201": {"001": "households", "002": "no_vehicle_households"},
    "b01003": {"001": "population"},
}


def parse_acs(series, income=False):
    """Keep source tokens separately; turn unavailable values into NaN, flag bound estimates."""
    raw = series.astype(str).str.strip()
    numeric = pd.to_numeric(raw.str.replace(",", "", regex=False).str.replace("+", "", regex=False)
                            .str.replace("-", "", regex=False).where(~raw.str.startswith("-"), raw), errors="coerce")
    annotation = pd.Series("", index=raw.index, dtype=str)
    absent = numeric.isna() | numeric.lt(0)
    annotation.loc[absent] = raw.loc[absent].replace("", "missing")
    numeric = numeric.mask(absent)
    if income:
        # ACS median income uses 250001 and 2499 as upper/lower bound codes.
        upper = raw.str.endswith("+") | numeric.eq(250001)
        lower = raw.str.endswith("-") | numeric.eq(2499)
        annotation.loc[upper] = "250,000+ (upper category; not an exact median)"
        annotation.loc[lower] = "2,500- (lower category; not an exact median)"
        numeric = numeric.mask(upper, 250000).mask(lower, 2500)
    return numeric.astype(float), annotation


def load_tracts(ledger):
    tracts = gpd.read_file(RAW / "tl_2024_36_tract.zip")
    n = len(tracts)
    tracts = tracts.loc[tracts.COUNTYFP.isin(COUNTIES)].copy()
    ledger.append(dict(stage="tracts", step="outside_nyc_counties", before=n, affected=n-len(tracts),
                       after=len(tracts), action="exclude", reason="Five NYC counties define the study area"))
    assert tracts.GEOID.is_unique
    invalid = ~tracts.geometry.is_valid
    ledger.append(dict(stage="tracts", step="repair_invalid_geometry", before=len(tracts), affected=int(invalid.sum()),
                       after=len(tracts), action="repair", reason="Valid polygons are required for spatial predicates"))
    if invalid.any():
        tracts.loc[invalid, "geometry"] = tracts.loc[invalid].geometry.make_valid()
    usable = tracts.geometry.notna() & ~tracts.geometry.is_empty & tracts.geometry.is_valid
    ledger.append(dict(stage="tracts", step="unusable_geometry", before=len(tracts), affected=int((~usable).sum()),
                       after=int(usable.sum()), action="exclude", reason="No usable polygon after repair"))
    tracts = tracts.loc[usable, ["GEOID", "COUNTYFP", "NAME", "ALAND", "geometry"]].to_crs(CRS)
    tracts["borough"] = tracts.COUNTYFP.map(COUNTIES)
    tracts["land_km2"] = pd.to_numeric(tracts.ALAND) / 1_000_000
    for table, fields in ACS_FIELDS.items():
        columns = ["GEO_ID"] + [f"{table.upper()}_{kind}{line}" for line in fields for kind in ["E", "M"]]
        pieces, all_rows = [], 0
        for chunk in pd.read_csv(RAW / f"acsdt5y2024-{table}.dat", sep="|", dtype=str,
                                 keep_default_na=False, usecols=columns, chunksize=100_000):
            all_rows += len(chunk)
            mask = chunk.GEO_ID.str.startswith(tuple("1400000US36" + c for c in COUNTIES))
            pieces.append(chunk.loc[mask].copy())
        acs = pd.concat(pieces, ignore_index=True)
        acs["GEOID"] = acs.GEO_ID.str.replace("1400000US", "", regex=False)
        assert acs.GEOID.str.fullmatch(r"\d{11}").all() and acs.GEOID.is_unique
        ledger.append(dict(stage="acs", step=f"{table}_outside_nyc_tracts", before=all_rows,
                           affected=all_rows-len(acs), after=len(acs), action="exclude",
                           reason="Summary files contain all published national geographies; retain NYC tracts only"))
        output = acs[["GEOID"]].copy()
        for line, name in fields.items():
            for kind, suffix in [("E", ""), ("M", "_moe")]:
                col = name + suffix
                output[col + "_raw"] = acs[f"{table.upper()}_{kind}{line}"]
                output[col], output[col + "_annotation"] = parse_acs(output[col + "_raw"], income=(name == "income" and kind == "E"))
                ledger.append(dict(stage="acs", step=f"{col}_unavailable", before=len(output),
                                   affected=int(output[col].isna().sum()), after=len(output), action="set_missing",
                                   reason="Unavailable/suppressed ACS tokens are not zero"))
        tracts = tracts.merge(output, on="GEOID", how="left", validate="one_to_one")
    tracts["income_censored"] = tracts.income_annotation.fillna("").str.contains("category")
    tracts["income_imprecise"] = tracts.income_moe.gt(tracts.income * 0.5)
    tracts["no_vehicle_share"] = tracts.no_vehicle_households / tracts.households.where(tracts.households.gt(0))
    invalid_share = ~tracts.no_vehicle_share.between(0, 1) & tracts.no_vehicle_share.notna()
    tracts.loc[invalid_share, "no_vehicle_share"] = np.nan
    ledger.append(dict(stage="acs", step="invalid_no_vehicle_share", before=len(tracts), affected=int(invalid_share.sum()),
                       after=len(tracts), action="set_missing", reason="Share must be between zero and one"))
    tracts["eligible"] = True
    for col in ["households", "population", "land_km2"]:
        before = int(tracts.eligible.sum())
        excluded = tracts.eligible & ~tracts[col].gt(0)
        tracts.loc[excluded, "eligible"] = False
        ledger.append(dict(stage="residential_comparison", step=f"nonpositive_or_missing_{col}", before=before,
                           affected=int(excluded.sum()), after=int(tracts.eligible.sum()), action="exclude_from_comparison",
                           reason="Residential rate comparisons need positive households, population, and land area; tract stays mapped"))
    return tracts.sort_values("GEOID").reset_index(drop=True)


def assign_points(points, tracts, id_column):
    """Intersect once; shared-boundary ties go to lexicographically first GEOID and are flagged."""
    joined = gpd.sjoin(points, tracts[["GEOID", "borough", "geometry"]], how="left", predicate="intersects")
    matches = joined.groupby(id_column).GEOID.count()
    joined["tract_matches"] = joined[id_column].map(matches).astype(int)
    joined = joined.sort_values([id_column, "GEOID"], na_position="last").drop_duplicates(id_column)
    assert joined[id_column].is_unique and len(joined) == len(points)
    return joined.drop(columns=["index_right"], errors="ignore")


def locate_stations(endpoint_table, tracts):
    ordered = endpoint_table.sort_values(["station_id", "observations", "latitude", "longitude"],
                                         ascending=[True, False, True, True])
    stations = ordered.drop_duplicates("station_id").copy()
    group = endpoint_table.groupby("station_id")
    stations["endpoint_observations"] = stations.station_id.map(group.observations.sum())
    stations["coordinate_pairs"] = stations.station_id.map(group.size())
    stations["modal_share"] = stations.observations / stations.endpoint_observations
    stations = gpd.GeoDataFrame(stations, geometry=gpd.points_from_xy(stations.longitude, stations.latitude), crs="EPSG:4326").to_crs(CRS)
    locations = gpd.GeoDataFrame(endpoint_table.copy(), geometry=gpd.points_from_xy(endpoint_table.longitude, endpoint_table.latitude), crs="EPSG:4326").to_crs(CRS)
    modes = stations.set_index("station_id").geometry
    locations["distance_from_mode_m"] = locations.geometry.distance(gpd.GeoSeries(locations.station_id.map(modes), crs=CRS))
    stations["max_displacement_m"] = stations.station_id.map(locations.groupby("station_id").distance_from_mode_m.max())
    stations["location_review_flag"] = stations.max_displacement_m.gt(100)
    stations = assign_points(stations, tracts, "station_id")
    locations = locations.drop(columns="geometry")
    return stations, locations


def locate_coordinate_starts(coordinates, tracts):
    if coordinates.empty:
        result = coordinates.copy()
        result["GEOID"] = pd.Series(dtype=str)
        result["borough"] = pd.Series(dtype=str)
        return result
    unique = coordinates[["latitude", "longitude"]].drop_duplicates().reset_index(drop=True)
    unique["point_id"] = unique.index
    points = gpd.GeoDataFrame(unique, geometry=gpd.points_from_xy(unique.longitude, unique.latitude), crs="EPSG:4326").to_crs(CRS)
    joined = assign_points(points, tracts, "point_id")
    return coordinates.merge(joined[["latitude", "longitude", "GEOID", "borough", "tract_matches"]],
                             on=["latitude", "longitude"], how="left", validate="many_to_one")
