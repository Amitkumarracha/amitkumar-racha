# Checks, thresholds and limitations

Detailed reference for the checker; the short run instructions are in [README.md](../README.md).

## Checks and thresholds

Rules combine independent evidence where available. They are screening decisions, not a claim that unflagged instruments are calibrated.

| Check | Evidence and behavior |
|---|---|
| Input integrity | Validates metadata, required fields, exact minute timestamps and finite numeric values; reports bad cells, absent files, off-grid records and missing intervals. A wholly unusable pack exits with a useful error and status 2. |
| GPS | Validates NMEA XOR checksums, RMC date/time, active/void status and coordinate ranges; validates understood GGA fix/position/height fields. Missing checksums, void fixes and malformed messages cannot support a correction. Rejections remain private diagnostic counts, not automatic weather exclusions. |
| Clock epochs | At least three consecutive trusted RMC fixes spanning two hours with a consistent minute offset. A transition must match one unique source-order timestamp discontinuity inside the GPS transition bracket. Offsets beyond a day or ambiguous evidence are not applied; unresolved supported conflicts are withheld. Corrections precede sorting and deduplication. |
| Replayed records | Drops later exact copies after clock correction and retains the first copy. Different values sharing a time are excluded as ambiguous. Private diagnostics preserve source CSV line numbers and original labels. |
| Broad physical screens | Temperature −90…60°C; RH 0…103%; station pressure 300…1100 hPa; mean wind 0…250 km/h; direction 0…360°; GHI −5…1600 W/m²; nonnegative rain up to 600 mm/hour equivalent. Review these broad screens outside this network's documented units and geography. |
| Humidity | Overshoots up to 103% are provisionally retained without clamping. A ≥12-hour run at ≥99% is excluded when over half its values exceed 100% and some exceed 103%. Saturation alone is not a fault. |
| Flatlines / spikes | Exact temperature/pressure flatlines ≥6 hours, or interior RH flatlines ≥12 hours. RH at 0/100% is not rejected by the flatline rule alone. Isolated temperature/pressure spikes require >12°C/>8 hPa jumps on both sides (scaled for coarser sampling) and immediate return within two units on consecutive intervals. |
| Peers | Up to four nearby stations within 100 km and 700 m elevation difference, with at least two available per comparison. Uses locally screened, clock-corrected data. Compares pressure residual changes, not equal raw pressures at different elevations. |
| Pressure steps | A ≥3 hPa interval jump, ≥4 hPa peer-residual shift, low scatter on both sides and persistence on ≥80% of remaining days. Withholds later pressure; absolute calibration remains unknown. |
| Wind scale | ≥7 daily ratios on each side, with ≥18 hours of paired target/peer observations per day, a factor outside 0.5…2, persistent separation and a stable later level. Daily and hourly means use identical UTC samples, preventing selective outages from mimicking a scale change. Refines onset to a sustained hourly interval. Withholds affected wind; no multiplier is inferred from peers. |
| Sunlight heating | ≥21 qualified daily bright/dark comparisons, ≥2°C growth, a positive robust trend and stable nighttime residual. A five-day median sets a conservative detection date. Excludes only ≥500 W/m² intervals after it; earlier onset is unresolved. |
| Zero response / rain | Wind/sunlight zero runs need ≥24/48 hours and active peers. Rain blockage needs ≥2 days of zero, ≥2 peers each collecting ≥5 mm, plus a ≥10 mm release or nearby rain-hardware obstruction/clearing note. Release evidence uses screened values in at most three immediately consecutive intervals; it cannot cross a telemetry gap. Evidence notes state the actual observation count. No rain redistribution or interpolation. |
| Genuine events | Retains temperature in ≥2-hour episodes corroborated at ≥3 stations: ≥8°C warming against the same UTC hours of preceding days, RH <25%, wind ≥15 km/h. Does not override another channel's exclusions. |
| Maintenance | Dates and keywords corroborate pressure, wind and rain findings. Vague note times never establish exact UTC boundaries. |

This layered approach follows the physical, temporal and spatial principles in [NOAA MADIS surface QC](https://madis.ncep.noaa.gov/madis_sfc_qc.shtml). NMEA interpretation follows [Trimble RMC](https://receiverhelp.trimble.com/oem-gnss/nmea0183-messages-rmc.html) and [GGA](https://receiverhelp.trimble.com/oem-gnss/nmea0183-messages-gga.html) documentation. Thresholds above are this checker's explicit choices, not claimed NOAA-mandated thresholds.

## Output and interpretation

Exactly these columns:

```text
station_id,channel,start_utc,end_utc,issue,action,note
```

Bounds are inclusive sample-end UTC labels (`YYYY-MM-DD HH:MM`). Channel is a source column name, `all` or `metadata`. Clock-correction bounds are **corrected** UTC; the note identifies original CSV rows and the transformation. Replay correction drops later copies, not all observations on that day. Missing intervals are unavailable, not fabricated observations.

- `exclude`: omit the unreliable channel/interval from its summary.
- `correct`: apply the explicit evidenced transformation; retain recoverable observations.
- `keep`: retain the evidenced weather or provisionally retain data with a metadata caveat; conflicting locations remain unresolved rather than arbitrarily corrected.

The checker produces flags, not a cleaned replacement dataset. Report coverage uses the same corrected/deduplicated in-memory records and exclusions. Coverage counts available screened measurements; it does not certify an entire climate record. Do not turn incomplete rain totals into full-window totals or present six weeks as a whole spring season.

For private row-by-row verification:

```bash
python checker.py /absolute/path/to/data-pack --diagnostics .private/diagnostics
```

Diagnostic CSVs preserve source order, CSV line number, original timestamp, corrected timestamp and replay status. JSON records GPS rejections, peer selection and rule evidence. These are private pack derivatives: never commit or share them. The original pack README is preserved locally as `.private/data-pack-README.md`.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests use temporary synthetic packs, covering normal readings, gaps, irregular intervals, replay copies, conflicting times, GPS-backed resets, source identity, flatlines, spikes, physical bounds, saturation, GPS validation, location conflicts, pressure/wind changes, sunlight heating, zero-response sensors, delayed rain, corroborated weather, malformed inputs, alternate IDs/dates, output format, deterministic CLI output and report coverage. No supplied data is embedded in the tests.

Accuracy regressions also cover selectively missing windy hours, rain after a telemetry gap, unrelated solar-panel cleaning, invalid rain-release values, a truncated release window and maintenance evidence without a recorded release. These test specific false-alarm risks; they do not establish a numerical accuracy score on an independently labeled pack.

## Assumptions and limits

- A shared network window is inferred from earliest/latest corrected records. A station may legitimately have started later, so edge gaps need deployment-history review.
- Only documented RMC/GGA fields are understood; fractional GPS seconds are not used for minute-resolution weather correction. GPS is an independent reference under the pack's stated logger/GPS relationship, not proof against every receiver fault.
- Plausible numbers in the wrong units cannot always be detected; units must remain those documented by the pack. Thresholds and sparse-peer fallbacks need review for different climates, elevations and resolutions.
- Cross-station checks need enough history and relevant peers. Elevation filters reduce obvious mismatches but do not model terrain or every local storm. Uncertain peer locations can affect comparisons.
- Rain-hardware keywords are corroboration, not a full interpretation of the notebook. Without a release, a relevant obstruction/clearing note is required; local rainfall differences can still make a suspected blockage uncertain.
- The sunlight rule detects significant later drift; it does not certify earlier daytime temperatures or establish the exact onset. The report defers full-window maximum/trend claims there. Gradual pressure faults without a jump, absolute sensor accuracy and snow catch are not comprehensively assessed.
- A wind change's boundary is hourly; the preceding partial hour may need review. No speculative pressure, wind, location or rainfall correction is applied.
- This is a batch tool, not an unattended 500-station service: no persisted history, alert escalation, calibration registry or operational monitoring is implemented. No unseen assessment pack was available to test.

