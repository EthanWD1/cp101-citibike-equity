# Station location review

The complete endpoint audit flagged one ID whose locations span more than 100 meters: **5348.06** in Brooklyn.

| Latitude | Longitude | Endpoint observations | Distance from mode | Intersecting tract |
|---:|---:|---:|---:|---|
| 40.71797941 | -73.96427449 | 383 | 0 m | 36047055500 |
| 40.7188000 | -73.9610000 | 6 | 291.2 m | 36047055500 |

The modal location accounts for **383 / 389 = 98.46%** of this station ID's valid endpoint observations. The alternative pair was spatially checked against the same 2024 TIGER tracts in EPSG:32618: both points fall in tract **36047055500**. Therefore choosing either recorded pair would leave this station's tract-level coverage and departure assignment unchanged. The workflow retains the modal location and records the flag; no manual coordinate override was applied.

This review checks the observed coordinate inconsistency, not the station's operating history. First/last-week observation and broader tract-boundary accessibility sensitivity remain final-project work. Coordinate pairs and frequencies are retained in `data/processed/station_coordinate_audit.csv`; the unchanged trip archive preserves the original source precision.
