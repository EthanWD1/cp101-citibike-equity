"""Chunked, deterministic cleaning and endpoint/station aggregation."""
from collections import Counter
from pathlib import Path
import sqlite3
from zipfile import ZipFile

import numpy as np
import pandas as pd

from .config import RAW, START, STOP

COLUMNS = ["ride_id", "started_at", "ended_at", "start_station_id", "end_station_id",
           "start_lat", "start_lng", "end_lat", "end_lng", "member_casual"]


def valid_coordinates(lat, lon):
    """Worldwide numeric coordinates; exclude the missing-coordinate (0, 0) placeholder."""
    return lat.between(-90, 90) & lon.between(-180, 180) & ~((lat == 0) & (lon == 0))


class RideDeduplicator:
    """SQLite keeps global ride IDs on disk instead of holding millions in notebook memory."""
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(str(path))
        self.db.execute("PRAGMA journal_mode=OFF")
        self.db.execute("PRAGMA synchronous=OFF")
        self.db.execute("CREATE TABLE IF NOT EXISTS seen (id TEXT PRIMARY KEY) WITHOUT ROWID")
        self.db.execute("DELETE FROM seen")

    def keep(self, ids):
        unique = ids.drop_duplicates()
        already = set()
        values = unique.tolist()
        for start in range(0, len(values), 900):
            batch = values[start:start + 900]
            query = "SELECT id FROM seen WHERE id IN (" + ",".join("?" for _ in batch) + ")"
            already.update(row[0] for row in self.db.execute(query, batch))
        keep = ~ids.duplicated() & ~ids.isin(already)
        self.db.executemany("INSERT INTO seen VALUES (?)", ((x,) for x in ids[keep]))
        self.db.commit()
        return keep

    def close(self):
        self.db.close()


def counter_frame(counter, columns, value="departures"):
    return pd.DataFrame([(*key, n) for key, n in sorted(counter.items())], columns=columns + [value])


def clean_chunk(frame, deduplicator):
    """Return retained September starts and disjoint exclusion counts."""
    frame = frame.copy()
    for field in ["ride_id", "start_station_id", "end_station_id", "member_casual"]:
        frame[field] = frame[field].str.strip()
    counts = {"raw_rows": len(frame)}
    valid_id = frame.ride_id.ne("")
    counts["missing_ride_id"] = int((~valid_id).sum())
    frame = frame.loc[valid_id].copy()
    keep = deduplicator.keep(frame.ride_id)
    counts["duplicate_ride_id"] = int((~keep).sum())
    frame = frame.loc[keep].copy()
    started = pd.to_datetime(frame.started_at, format="mixed", errors="coerce")
    counts["invalid_start_time"] = int(started.isna().sum())
    in_period = started.ge(START) & started.lt(STOP)
    counts["outside_september"] = int((started.notna() & ~in_period).sum())
    frame = frame.loc[in_period].copy()
    frame["date"] = started.loc[in_period].dt.strftime("%Y-%m-%d")
    frame["member_casual"] = frame.member_casual.where(frame.member_casual.isin(["member", "casual"]), "unknown")
    for side in ["start", "end"]:
        for coord in ["lat", "lng"]:
            col = f"{side}_{coord}"
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame[f"{side}_coord_valid"] = valid_coordinates(frame[f"{side}_lat"], frame[f"{side}_lng"])
    frame["end_time_valid"] = pd.to_datetime(frame.ended_at, format="mixed", errors="coerce").notna()
    counts["retained_september"] = len(frame)
    return frame, counts


def aggregate_trips(archive=None, chunk_size=200_000):
    archive = archive or RAW / "202509-citibike-tripdata.zip"
    cache = Path(".cache")
    cache.mkdir(exist_ok=True)
    dedup = RideDeduplicator(cache / "ride_ids.sqlite")
    totals, endpoints, departures, coordinate_only = Counter(), Counter(), Counter(), Counter()
    missing_audits, raw_audits, file_audits = [], [], []
    try:
        with ZipFile(archive) as zipped:
            members = sorted(n for n in zipped.namelist() if n.lower().endswith(".csv") and not n.startswith("__MACOSX"))
            if len(members) != 6:
                raise ValueError(f"Expected six September 2025 CSVs; found {len(members)}")
            for member in members:
                file_counts = Counter()
                with zipped.open(member) as stream:
                    for chunk in pd.read_csv(stream, usecols=COLUMNS, dtype=str, keep_default_na=False, chunksize=chunk_size):
                        raw_times = pd.to_datetime(chunk.started_at, format="mixed", errors="coerce")
                        raw_audit = pd.DataFrame({"date": raw_times.dt.strftime("%Y-%m-%d").fillna("unparseable"),
                            "member_casual": chunk.member_casual.where(chunk.member_casual.isin(["member", "casual"]), "unknown"),
                            "input_rows": 1, "missing_ride_id": chunk.ride_id.str.strip().eq("").astype(int),
                            "invalid_start_time": raw_times.isna().astype(int),
                            "outside_september": (raw_times.notna() & ~(raw_times.ge(START) & raw_times.lt(STOP))).astype(int)})
                        raw_audits.append(raw_audit.groupby(["date", "member_casual"], as_index=False).sum())
                        frame, counts = clean_chunk(chunk, dedup)
                        totals.update(counts)
                        file_counts.update(counts)
                        audit = frame[["date", "member_casual"]].copy()
                        audit["retained_starts"] = 1
                        for side in ["start", "end"]:
                            audit[f"missing_{side}_id"] = frame[f"{side}_station_id"].eq("").astype(int)
                            audit[f"invalid_{side}_coordinates"] = (~frame[f"{side}_coord_valid"]).astype(int)
                        audit["invalid_end_time"] = (~frame.end_time_valid).astype(int)
                        missing_audits.append(audit.groupby(["date", "member_casual"], as_index=False).sum())
                        for side in ["start", "end"]:
                            valid = frame[f"{side}_station_id"].ne("") & frame[f"{side}_coord_valid"]
                            grouped = frame.loc[valid].groupby([f"{side}_station_id", f"{side}_lat", f"{side}_lng"]).size()
                            endpoints.update(grouped.to_dict())
                        valid_start = frame.start_station_id.ne("")
                        departures.update(frame.loc[valid_start].groupby(["start_station_id", "date", "member_casual"]).size().to_dict())
                        coord_only = ~valid_start & frame.start_coord_valid
                        coordinate_only.update(frame.loc[coord_only].groupby(["start_lat", "start_lng", "date", "member_casual"]).size().to_dict())
                file_audits.append({"file": member, **file_counts})
                print(f"Processed {member}: {file_counts['raw_rows']:,} records", flush=True)
    finally:
        dedup.close()
        (cache / "ride_ids.sqlite").unlink(missing_ok=True)
    endpoint_table = counter_frame(endpoints, ["station_id", "latitude", "longitude"], "observations")
    daily_stations = counter_frame(departures, ["station_id", "date", "member_casual"])
    coordinate_starts = counter_frame(coordinate_only, ["latitude", "longitude", "date", "member_casual"])
    missing = pd.concat(missing_audits, ignore_index=True).groupby(["date", "member_casual"], as_index=False).sum()
    raw_audit = pd.concat(raw_audits, ignore_index=True).groupby(["date", "member_casual"], as_index=False).sum()
    ledger = []
    before = totals["raw_rows"]
    reasons = {
        "missing_ride_id": "Cannot establish a unique trip for deduplication",
        "duplicate_ride_id": "One trip per ride ID, first occurrence in sorted archive/file order",
        "invalid_start_time": "Cannot assign the trip to September or a day",
        "outside_september": "Start must be September 1–30, 2025, in the published local timestamp",
    }
    for step, reason in reasons.items():
        removed = totals[step]
        ledger.append({"stage": "trips", "step": step, "before": before, "affected": removed,
                       "after": before - removed, "action": "exclude", "reason": reason})
        before -= removed
    assert before == totals["retained_september"]
    return {"totals": dict(totals), "ledger": ledger, "endpoints": endpoint_table,
            "station_daily": daily_stations, "coordinate_only": coordinate_starts,
            "missingness": missing, "raw_date_audit": raw_audit, "files": pd.DataFrame(file_audits)}
