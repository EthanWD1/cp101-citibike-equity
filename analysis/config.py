"""Study definitions; paths are relative to the project root."""
from pathlib import Path

RAW = Path("data/raw")
PROCESSED = Path("data/processed")
FIGURES = Path("visualizations")
CRS = "EPSG:32618"
COUNTIES = {"005": "Bronx", "047": "Brooklyn", "061": "Manhattan",
            "081": "Queens", "085": "Staten Island"}
BOROUGHS = list(COUNTIES.values())
SCOPES = ["NYC"] + BOROUGHS
GROUPS = ["Q1", "Q2", "Q3", "Q4"]
START = "2025-09-01"
STOP = "2025-10-01"
ACS_BASE = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/"
WATER_SOURCES = {
    f"tl_2024_36{county}_areawater.zip":
        f"https://www2.census.gov/geo/tiger/TIGER2024/AREAWATER/tl_2024_36{county}_areawater.zip"
    for county in COUNTIES
}
SOURCES = {
    "202509-citibike-tripdata.zip": "https://s3.amazonaws.com/tripdata/202509-citibike-tripdata.zip",
    "tl_2024_36_tract.zip": "https://www2.census.gov/geo/tiger/TIGER2024/TRACT/tl_2024_36_tract.zip",
    **{f"acsdt5y2024-{t}.dat": ACS_BASE + f"acsdt5y2024-{t}.dat"
       for t in ["b01003", "b08201", "b19013"]},
    **WATER_SOURCES,
}
