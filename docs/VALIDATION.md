# Local validation — reviewed 25 October 2026

## Recording and repository cleanup — 25 October

- The applicant explicitly authorized reviewed commits/pushes and removal of unnecessary public preparation files. The tested accuracy fix is checkpoint `5db2840`; the existing initial commit is preserved, with no history rewriting.
- The final workspace rerun passed **51 tests in 20.22 seconds**. Running the checker against the relocated `private_data/` pack still yields **40 flags**; the independent audit still verifies all **40 flags** and **56 coverage counts**.
- An isolated copy containing only the staged public repository files, without the supplied pack or private helpers, passed **51 tests in 42.81 seconds**. Genuine output is saved locally for the recording. All public Markdown file links resolve, and the reviewed public tree contains 16 files with no supplied raw records.
- Required root deliverables remain: code, `DECISIONS.md`, `flags.csv`, `report.pdf` and the short README. Check details and this validation record moved to `docs/`. Duplicate generated HTML/coverage and preparation notes are local-only; the submitted PDF is unchanged.
- The supplied pack moved to ignored `private_data/`; the assignment PDF and recording materials moved to ignored `waste/`. All **20 original hashes** still match using a private relocation map. Public AI-log provenance remains in `ai_logs/`; complete conversation masters remain private and require permitted delivery.
- The recording guide now selects the actual S04 sunlight-bias flag rather than its earlier retained weather event. Local notes contain the full narration, exact source-evidence commands and folder structure.
- The applicant's own decisions/manual calculation, recording link, complete AI-log delivery, exact invitation deadline and submission form remain unfinished. Publishing the reviewed code does not complete those requirements.

## Accuracy review — 25 October

- Re-read the assignment PDF, source code, tests, report, submission checklist, recording guide and AI-log delivery status.
- Reproduced three false alarms with new synthetic packs before fixing the code: selective loss of windy hours, later rainfall after a telemetry gap, and solar-panel cleaning incorrectly used as rain-gauge evidence.
- Wind daily/hourly comparisons now use matching UTC observations and require 18 paired hours per qualified day. Rain-release evidence now stops at gaps, uses screened values and reports the actual available count; maintenance corroboration requires rain-hardware context.
- Added six regression cases, including invalid release values, a shortened release window and an actual gauge-clearing note without a measured release. Final full run: **51 passed in 20.75 seconds**, with no warnings.
- Regenerated `flags.csv`, private diagnostics, `report.html`, `coverage.csv` and `report.pdf`. All **40 station/channel/interval/issue/action decisions** match the reviewed baseline: **24 exclude, 2 correct, 14 keep**. Fifteen evidence notes changed: rain-release wording and consistent two-decimal sunlight evidence. No decision thresholds were tuned to the supplied station IDs or dates.
- Re-ran the independent source audit: **40/40 flags** and **56/56 channel counts** checked; no keep/exclude channel conflict. These are checks of evidence and accounting, not independently labeled ground truth or a measured accuracy percentage.
- Confirmed the regenerated PDF is **one A4 page** and visually inspected the complete rendered page. All **20 original-input hashes** remain unchanged. Protected input paths are ignored and absent from tracked files and reachable Git history; no exact source-record text was found in tracked artifacts.
- Found the existing local commit `608c68d` (`Finalize project structure and README`) and verified signed-out access to the existing public [repository](https://github.com/Amitkumarracha/amitkumar-racha). Its published README still describes the earlier 45-test revision; this review's changes remain local. This review did not stage, commit, push, publish or submit anything. The earlier zero-commit statements below describe the initial implementation only.
- Refreshed authentic private AI-chat exports through the recorded cutoff. Complete assessment delivery still needs a permitted route because original tool outputs include supplied data; refresh again after the last chat turn.

The six additional cases reduce demonstrated false-alarm risks. No independently labeled unseen pack is available, so a numerical accuracy claim would be unsupported.

## Initial implementation checks — 24 October

- `python -m pytest -q`: **45 passed in 17.68 seconds** at implementation completion; the submission review rerun produced **45 passed in 15.76 seconds**, with no warnings.
- `python checker.py . --diagnostics .private/diagnostics`: **40 flags**; the supplied raw pack remains local and ignored.
- `python build_report.py .`: accepted the matching flags and generated the HTML report and coverage counts.
- Independent source audit: **40/40 flags verified**, **56/56 station/channel counts verified**, with no retained-temperature interval overlapping an exclusion for that channel.
- Headless Chromium printed the report; `pdfinfo` confirmed **one A4 page**. The rendered page was visually inspected for clipped or missing text. The checked snapshot is `report.pdf`.
- All **20 original-input SHA-256 hashes** match, including the preserved original README in `.private/`. The submission README replaces the root documentation; the original survives unchanged privately.
- At initial implementation, no commits had been created and no files were staged or tracked. Ignore rules cover the supplied weather/GPS files, metadata, notes, assignment PDF and private diagnostics.

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

`DECISIONS.md` is an author worksheet, not a finished personal statement. The manual solar calculation is unanswered. The supplied applicant name/email are now filled in the short README. The recording, finished personal decisions, exact deadline, complete-log delivery, review of the latest changes for publication, and submission form remain outstanding.

## Submission review improvements

- Re-read all eight PDF pages and compared each submission requirement with the current files; the PDF gives no numerical scoring weights.
- Shortened the root README and moved detailed thresholds and limitations into `CHECKS.md`.
- Strengthened `.gitignore` to cover CSV/NMEA copies, while explicitly allowing the required root `flags.csv` and aggregate `coverage.csv`. Original inputs, diagnostic derivatives and conversation masters remain ignored.
- Recovered an authentic chronological conversation export from the first assignment prompt. JSONL and readable HTML masters live under `.private/ai_logs/`, with a public provenance/count/hash manifest and delivery index in `ai_logs/`.
- Verified the exported contents against the recorded source and detected original supplied-data records in tool results. Public log delivery is therefore still unfinished: use a permitted confidential route and refresh the snapshot after the final turn. The manifest/index alone do not satisfy the complete-chat requirement.
- The initial submission review confirmed the configured remote repository basename was `amitkumar-racha`; it had not yet verified public access. The 25 October review above now verifies that access. No agent commit, push or form submission was performed.
