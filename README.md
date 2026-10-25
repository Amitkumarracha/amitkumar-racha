Full Name: Amitkumar Racha
Email: amitkumar.racha.btech2023@sitpune.edu.in
Video: [UNLISTED VIDEO LINK REQUIRED]
Run: `python checker.py /path/to/data-pack`

# Weather-network quality review

The checker identifies unreliable sensor periods, recovers GPS-proven clock errors and retains corroborated weather extremes. It reads the private data pack without modifying it. The one-page [report](report.pdf) recommends visiting S07 to verify the replacement anemometer and logger conversion, with S04 as the runner-up.

## Run and test

Python 3.10+; all dependencies are free:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python checker.py /absolute/path/to/data-pack
python -m pytest -q
```

The pack contains `stations.csv`, `data/`, `gps/` and maintenance notes. It is intentionally absent from the public repository. Run from the desired output directory: the checker writes `flags.csv` there. In the applicant's local workspace, `python checker.py private_data` reads the ignored pack. Reviewers should pass their own pack path. Station IDs, intervals and anomaly dates are discovered rather than hardcoded.

The seven output fields are `station_id,channel,start_utc,end_utc,issue,action,note`. Bounds are inclusive sample-end UTC labels. Actions are `exclude`, `correct` or `keep`; correction notes explain the transformation.

## What is checked

- Schema, numeric values, sampling gaps, replay copies and ambiguous repeated times.
- GPS checksums, valid fixes, location conflicts and independently supported clock changes.
- Broad physical bounds, flatlines, isolated spikes and persistent humidity overshoot.
- Pressure steps, wind scale changes, sunlight-linked temperature drift and blocked rain gauges, using peer and maintenance evidence.
- Corroborated warm, dry, windy events retained without overriding another channel's exclusions.

[CHECKS.md](docs/CHECKS.md) documents thresholds, units and assumptions. [VALIDATION.md](docs/VALIDATION.md) records the executed tests and source checks. This pack produces 40 flag intervals; the synthetic suite currently has 51 passing cases, including selective wind outages and misleading rain-release evidence.

Rebuild the report and aggregate coverage after generating flags:

```bash
python build_report.py /absolute/path/to/data-pack
```

This refuses stale flags and generates local `report.html` and `coverage.csv` intermediates. Print the HTML to A4 PDF after a report change; `report.pdf` is the submitted report. Optional source-row audits use `--diagnostics .private/diagnostics`; never publish those files.

The repository root contains the code, required deliverables and dependency/test configuration. `tests/` holds synthetic cases, `docs/` holds check details and validation, and `ai_logs/` records conversation provenance and delivery status. The local `private_data/`, `.private/` and `waste/` folders are ignored; `waste/` holds recording notes, the assignment PDF and generated copies for the applicant to review.

## Limits and submission status

No speculative calibration or rainfall reconstruction is applied. S04's earlier heating-bias onset and S05's location conflict remain unresolved. Absolute calibration, snow catch and the assessor's unseen pack were not verified; this batch checker is not an unattended 500-station service.

Before submission, finish [DECISIONS.md](DECISIONS.md) in your own words, do its solar calculation without AI/code, supply the recording above, and complete the authentic AI-log delivery described in [ai_logs/README.md](ai_logs/README.md).
