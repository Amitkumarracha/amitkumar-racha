# Local validation — 24 October 2026

## Executed checks

- `python -m pytest -q`: **45 passed in 17.68 seconds** at implementation completion; the submission review rerun produced **45 passed in 15.76 seconds**, with no warnings.
- `python checker.py . --diagnostics .private/diagnostics`: **40 flags**; the supplied raw pack remains local and ignored.
- `python build_report.py .`: accepted the matching flags and generated the HTML report and coverage counts.
- Independent source audit: **40/40 flags verified**, **56/56 station/channel counts verified**, with no retained-temperature interval overlapping an exclusion for that channel.
- Headless Chromium printed the report; `pdfinfo` confirmed **one A4 page**. The rendered page was visually inspected for clipped or missing text. The checked snapshot is `report.pdf`.
- All **20 original-input SHA-256 hashes** match, including the preserved original README in `.private/`. The submission README replaces the root documentation; the original survives unchanged privately.
- No commits were created and no files were staged or tracked. Ignore rules cover the supplied weather/GPS files, metadata, notes, assignment PDF and private diagnostics.

Environment: Python 3.14.7, pandas 3.0.5, NumPy 2.5.3, pytest 9.1.1. Dependency ranges permit other supported versions; those other versions were not separately tested.

## What the flags mean on this pack

There are **24 exclusion intervals**, **2 correction intervals**, and **14 keep intervals**. Counts describe intervals, not individual rejected observations; the sunlight rule produces separate bright periods rather than excluding verified nighttime data.

| Station | Verified result |
|---|---|
| S01 | No sensor exclusions; lower mountain temperature/pressure were not rejected for differing from low stations. One corroborated weather event is retained. |
| S02 | Pressure rises 6.5 hPa at 21 March 17:20 UTC with a persistent peer-residual shift. Later pressure is withheld; **2,984/6,048** pressure intervals remain. |
| S03 | **481** temperature readings form one exact flatline; **4** isolated spikes are excluded. **5,563/6,048** temperature intervals remain. |
| S04 | **374** strongly sunlit temperature intervals are withheld across 14 periods; **657** rain intervals are withheld around the blocked-gauge/release episode. Temperature/rain coverage: **5,674/6,048**, **5,391/6,048**. |
| S05 | A **505-reading** humidity episode includes **451** values above 100%; **5,543/6,048** humidity intervals remain. Valid GPS fixes conflict with the install coordinates by approximately **20.5 km**; neither source is automatically rewritten. |
| S06 | A GPS-proven **+360-minute** correction recovers **2,639** labels from source CSV rows **3411–6049**. All **6,048** observations remain unique and regularly spaced. |
| S07 | Wind-to-peer ratios fall to approximately **0.25** of their previous level and remain separated after replacement. The exclusion begins at the first sustained low hourly interval, **26 March 16:00 UTC**. **3,696/6,048** wind intervals remain. |
| S08 | **214** missing intervals from **16 March 14:00–18 March 01:30 UTC**; **144** exact replay copies covering 5 April. Keeping one copy leaves **5,834/6,048** intervals per channel. |

The visit recommendation is **S07**, with S04 the runner-up. The one-hour plan checks the replacement sensor model and logger conversion first, then verifies the result independently. The observed 0.25 ratio is not used as a calibration factor.

## Limits and unfinished submission tasks

S04's earlier temperature-bias onset remains unresolved: the rule first withholds bright intervals on 1 April, which does not certify earlier daytime data. S07's immediately preceding partial hour also needs review. Pressure and wind calibration, absolute instrument accuracy and snow capture are not established by this exercise. Synthetic alternate packs were tested; the assessor's unseen pack was unavailable.

`DECISIONS.md` is an author worksheet, not a finished personal statement. The manual solar calculation is unanswered. The supplied applicant name/email are now filled in the short README. The recording, finished personal decisions, exact deadline, approved Git history/publication and submission form remain outstanding.

## Submission review improvements

- Re-read all eight PDF pages and compared each submission requirement with the current files; the PDF gives no numerical scoring weights.
- Shortened the root README and moved detailed thresholds and limitations into `CHECKS.md`.
- Strengthened `.gitignore` to cover CSV/NMEA copies, while explicitly allowing the required root `flags.csv` and aggregate `coverage.csv`. Original inputs, diagnostic derivatives and conversation masters remain ignored.
- Recovered an authentic chronological conversation export from the first assignment prompt. JSONL and readable HTML masters live under `.private/ai_logs/`, with a public provenance/count/hash manifest and delivery index in `ai_logs/`.
- Verified the exported contents against the recorded source and detected original supplied-data records in tool results. Public log delivery is therefore still unfinished: use a permitted confidential route and refresh the snapshot after the final turn. The manifest/index alone do not satisfy the complete-chat requirement.
- Confirmed the configured remote repository basename is `amitkumar-racha`; GitHub visibility and external reviewer access have not been verified. No commit, push or form submission was performed.
