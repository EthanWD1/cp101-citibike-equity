import tempfile
import unittest
from pathlib import Path
import os
from zipfile import ZipFile

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point, box

from analysis.trips import RideDeduplicator, clean_chunk, aggregate_trips, valid_coordinates
from analysis.geography import assign_points, parse_acs, locate_stations
from analysis.metrics import assign_quartiles, calculate_metrics


def trip(ride_id="A", **changes):
    value = {"ride_id": ride_id, "started_at": "2025-09-01 12:00:00", "ended_at": "2025-09-01 12:10:00",
             "start_station_id": "001.00", "end_station_id": "002.00", "start_lat": "40.7", "start_lng": "-74",
             "end_lat": "40.71", "end_lng": "-74", "member_casual": "member"}
    return {**value, **changes}


class AnalysisTests(unittest.TestCase):
    def test_duplicates_across_chunks_and_string_station_ids(self):
        dedup = RideDeduplicator()
        first, counts = clean_chunk(pd.DataFrame([trip(), trip(), trip("B")]), dedup)
        second, counts2 = clean_chunk(pd.DataFrame([trip(), trip("C")]), dedup)
        self.assertEqual(counts["duplicate_ride_id"], 1)
        self.assertEqual(counts2["duplicate_ride_id"], 1)
        self.assertEqual(first.start_station_id.iloc[0], "001.00")
        self.assertEqual(second.ride_id.tolist(), ["C"])
        dedup.close()

    def test_destination_missing_does_not_remove_departure(self):
        dedup = RideDeduplicator()
        cleaned, counts = clean_chunk(pd.DataFrame([trip(end_station_id="", end_lat="", end_lng="", ended_at="")]), dedup)
        self.assertEqual(counts["retained_september"], 1)
        self.assertFalse(cleaned.end_coord_valid.iloc[0])
        self.assertFalse(cleaned.end_time_valid.iloc[0])
        dedup.close()

    def test_period_and_missing_id_exclusions(self):
        rows = [trip(""), trip("B", started_at="invalid"), trip("C", started_at="2025-10-01 00:00:00"),
                trip("D", started_at="2025-09-30 23:59:59"), trip("E", start_station_id="")]
        dedup = RideDeduplicator()
        frame, counts = clean_chunk(pd.DataFrame(rows), dedup)
        self.assertEqual([counts[k] for k in ["missing_ride_id", "invalid_start_time", "outside_september", "retained_september"]], [1, 1, 1, 2])
        self.assertTrue(frame.loc[frame.ride_id.eq("E"), "start_coord_valid"].iloc[0])
        dedup.close()

    def test_boundary_assignment_and_unmatched_points(self):
        polygons = gpd.GeoDataFrame({"GEOID": ["002", "001"], "borough": ["B", "A"]}, geometry=[box(1,0,2,1), box(0,0,1,1)], crs=32618)
        points = gpd.GeoDataFrame({"station_id": ["boundary", "inside", "outside"]}, geometry=[Point(1,.5), Point(.5,.5), Point(3,3)], crs=32618)
        assigned = assign_points(points, polygons, "station_id").set_index("station_id")
        self.assertEqual(assigned.loc["boundary", "GEOID"], "001")
        self.assertEqual(assigned.loc["boundary", "tract_matches"], 2)
        self.assertTrue(pd.isna(assigned.loc["outside", "GEOID"]))
        self.assertEqual(len(assigned), 3)

    def test_acs_missing_and_censored_values(self):
        values, annotations = parse_acs(pd.Series(["0", "-666666666", "N", "250001", "2499", "120000"]), income=True)
        self.assertEqual(values.iloc[0], 0)
        self.assertTrue(values.iloc[1:3].isna().all())
        self.assertEqual(values.iloc[3], 250000)
        self.assertEqual(values.iloc[4], 2500)
        self.assertIn("upper", annotations.iloc[3])

    def test_quartile_ties_are_not_split_and_missing_is_not_zero(self):
        result = assign_quartiles(pd.Series([1., 1., 2., 3., np.nan]), [1.,1.,2.])
        self.assertEqual(result.iloc[:4].tolist(), ["Q1", "Q1", "Q3", "Q4"])
        self.assertTrue(pd.isna(result.iloc[4]))

    def test_modal_station_location_and_coordinate_tie(self):
        polygons = gpd.GeoDataFrame({"GEOID": ["001"], "borough": ["Brooklyn"]},
                                   geometry=[box(-74, 40, -73, 41)], crs=4326).to_crs(32618)
        endpoints = pd.DataFrame({"station_id": ["A", "A", "B", "B"],
                                  "latitude": [40.70, 40.71, 40.72, 40.73],
                                  "longitude": [-73.9, -73.9, -73.9, -73.9],
                                  "observations": [10, 2, 5, 5]})
        stations, audit = locate_stations(endpoints, polygons)
        selected = stations.set_index("station_id")
        self.assertEqual(selected.loc["A", "latitude"], 40.70)
        self.assertEqual(selected.loc["B", "latitude"], 40.72)
        self.assertEqual(selected.loc["A", "endpoint_observations"], 12)
        self.assertTrue(selected.location_review_flag.all())
        self.assertEqual(len(audit), 4)

    def test_coordinate_bounds_and_missing_placeholder(self):
        mask = valid_coordinates(pd.Series([40.7, 0., 91., np.nan]), pd.Series([-74., 0., -74., -74.]))
        self.assertEqual(mask.tolist(), [True, False, False, False])

    def test_zero_coverage_and_empty_borough_usage(self):
        tracts = pd.DataFrame({"GEOID": ["001", "002"], "borough": ["Manhattan", "Staten Island"],
                               "eligible": [True, True], "income": [50000, 100000], "no_vehicle_share": [.8, .2],
                               "population": [1000, 1000], "land_km2": [1, 2]})
        stations = pd.DataFrame({"station_id": ["A"], "GEOID": ["001"], "borough": ["Manhattan"]})
        daily = pd.DataFrame({"station_id": ["A"], "date": ["2025-09-01"], "member_casual": ["member"], "departures": [20]})
        result, _, _, comparisons, correlations, _ = calculate_metrics(tracts, stations, daily, [])
        zero = result.loc[result.GEOID.eq("002")].iloc[0]
        self.assertEqual(zero.stations_per_km2, 0)
        self.assertTrue(pd.isna(zero.departures_per_station))
        self.assertTrue(comparisons.loc[comparisons.scope.eq("Bronx"), "status"].eq("empty group").all())
        self.assertTrue(correlations.loc[correlations.scope.eq("Staten Island"), "spearman_rho"].isna().all())

    def test_all_archive_members_and_coordinate_only_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            with ZipFile(archive, "w") as z:
                for i in range(6):
                    row = trip(str(i), start_station_id="" if i == 0 else "A", end_station_id="B")
                    z.writestr(f"part_{i}.csv", pd.DataFrame([row, row]).to_csv(index=False))
            previous = Path.cwd()
            try:
                os.chdir(tmp)
                results = aggregate_trips(archive, chunk_size=1)
            finally:
                os.chdir(previous)
            self.assertEqual(results["totals"]["raw_rows"], 12)
            self.assertEqual(results["totals"]["duplicate_ride_id"], 6)
            self.assertEqual(results["coordinate_only"].departures.sum(), 1)
            self.assertEqual(set(results["endpoints"].station_id), {"A", "B"})


if __name__ == "__main__":
    unittest.main()
