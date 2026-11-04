import unittest

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from analysis.config import SCOPES, GROUPS
from analysis.visualize import display_land, usage_cells, daily_summary


class VisualizationTests(unittest.TestCase):
    def test_water_changes_only_copy_geometry(self):
        original = gpd.GeoDataFrame({"GEOID":["001","002"],"eligible":[True,False],
                                    "land_km2":[.5,.2],"stations_per_km2":[10.,0.]},
                                   geometry=[box(0,0,2,2),box(3,0,4,1)],crs=32618)
        water = gpd.GeoDataFrame(geometry=[box(1,0,4,2)],crs=32618)
        before = original.copy(deep=True)
        result = display_land(original,water)
        self.assertTrue(original.equals(before))
        self.assertTrue(result.drop(columns="geometry").equals(before.drop(columns="geometry")))
        self.assertEqual(result.GEOID.tolist(),["001","002"])
        self.assertEqual(result.geometry.area.iloc[0],2.)
        self.assertTrue(result.geometry.is_valid.all())
        self.assertTrue(result.geometry.is_empty.iloc[1])

    def test_water_cannot_hide_eligible_tract(self):
        tracts = gpd.GeoDataFrame({"eligible":[True]},geometry=[box(0,0,1,1)],crs=32618)
        water = gpd.GeoDataFrame(geometry=[box(-1,-1,2,2)],crs=32618)
        with self.assertRaisesRegex(ValueError,"eligible"):
            display_land(tracts,water)

    def test_usage_empty_and_small_groups(self):
        comparisons = pd.DataFrame([{"scope":scope,"quartile":quartile,"variable":"income",
                                     "served_tracts":0,"departures_per_station_median":np.nan}
                                    for scope in SCOPES for quartile in GROUPS])
        comparisons.loc[0,["served_tracts","departures_per_station_median"]] = [2,100]
        records = usage_cells(comparisons,"income")
        self.assertEqual(records[0]["median"],100.)
        self.assertTrue(records[0]["small_group"])
        self.assertIsNone(records[1]["median"])
        self.assertFalse(records[1]["small_group"])

    def test_daily_calendar_includes_days_without_trips_and_excludes_unmatched(self):
        daily = pd.DataFrame({"GEOID":["001","001",None],"date":["2025-09-07","2025-09-01","2025-09-07"],
                              "member_casual":["casual"]*3,"departures":[80,220,1000]})
        pivot, summary = daily_summary(daily)
        self.assertEqual(len(pivot),30)
        self.assertEqual(summary["weekend_days"],8)
        self.assertEqual(summary["weekday_days"],22)
        self.assertEqual(summary["categories"]["casual"],
                         {"departures":300,"weekend_daily_mean":10.,"weekday_daily_mean":10.})


if __name__ == "__main__":
    unittest.main()
