# Submission checklist

## Readiness against the assignment PDF

| Requirement | Current status | Remaining action |
|---|---|---|
| Checker, one-command CLI, flags schema | Verified locally; 45 synthetic tests pass | Assessor's unseen pack is unavailable |
| Report at the repository root | One A4 page; both HTML and PDF present | Applicant should read and defend its recommendation |
| Short README with four opening lines | Shortened; supplied name/email filled; run command present | Add the actual recording link |
| `DECISIONS.md`, own words, ≤1½ pages | Author worksheet only | Applicant must write the answers and do the manual calculation |
| Complete AI chats from first prompt | Authentic local JSONL/HTML exports, with provenance manifest | Refresh after final turn and provide permitted assessor access; raw-data masters stay private |
| Three-minute recording with applicant's voice | Not provided | Record source evidence, uncertainty and recommendation; add unlisted link |
| Repository named `firstname-lastname` | Configured remote basename is `amitkumar-racha` | Verify GitHub visibility/access and intended publication timing |
| Genuine development commits | No commits or staging performed under the applicant's instruction | Obtain approval for real checkpoints; never fabricate past history |
| Submission form before deadline | Not submitted; exact deadline not supplied | Confirm invitation time, college/phone details, links and submit |

## Local deliverables

- [x] Run `python -m pytest -q` and review the actual result: 45 passed in the submission recheck.
- [x] Run `python checker.py /absolute/path/to/data-pack` from the repository root: 40 flags.
- [x] Run `python build_report.py /absolute/path/to/data-pack`; matching flags accepted.
- [x] Inspect the A4 report: one page, with no clipped or missing sections.
- [x] Confirm that `coverage.csv`, the report and `flags.csv` agree: all 56 channel counts checked.
- [x] Check all 40 flags against the private source records and review their evidence and uncertainty.
- [ ] Applicant reads the report and flags and can explain the strongest and least-certain decisions.
- [ ] Finish `DECISIONS.md` in your own words, including the manual question without AI/code; remove the worksheet prompts.
- [x] Fill the README name and email using details supplied by the applicant; retain the actual run command.
- [ ] Replace the README video placeholder with the working unlisted recording link.
- [x] Recover an authentic local conversation-content export from the first assignment prompt; preserve original failures and corrections.
- [ ] Refresh the export after the final turn and provide permitted assessor access. Resolve the actual data-sharing conflict described in `ai_logs/README.md` before publication.

## Three-minute recording — live files, your voice

- **0:00–0:20:** Explain the coordinator's two decisions and show the checker command.
- **0:20–1:20:** Strongest flag: open S06's original CSV around source rows 3408–3414 and GPS around the reboot; show the logger/GPS disagreement, the flag and the private timestamp audit. Explain why sorting/deduplicating first would lose real measurements.
- **1:20–2:20:** Least-certain flag: open S04's temperature/sunlight evidence and its flag; explain the daytime/nighttime comparison, the uncertain onset and the one independent check you want. Use another real flag if it is genuinely your least-certain decision.
- **2:20–3:00:** Show the report, recommend the visit, compare the runner-up, and state one important limitation. Use your own judgment and words.
- No slides or editing required. Check audio and the unlisted recording link. The screen may show the private data for the intended assessment; do not make the raw pack or recording public before the organizer permits it.

## Before any Git commit or publication

No commit, push, public repository creation or application submission is authorized by the current task. Ask the user for explicit approval before any of those actions.

- [ ] Confirm the repository name is `firstname-lastname` using the applicant's actual name.
- [ ] Check `git status --short --untracked-files=all`, `git ls-files`, and `git diff --cached --stat`.
- [ ] Inspect the exact staged paths and contents. Never use `git add .`.
- [ ] Keep `data/`, `gps/`, `stations.csv`, `maintenance_log.md`, `.private/`, the supplied PDF and all raw-record derivatives out of Git.
- [ ] Stage only explicitly reviewed submission files, then inspect them again.
- [ ] Make genuine incremental commits only with approval; do not fabricate a development history or backdate commits.
- [ ] Confirm there are no credentials, private exports or raw pack records in any public artifact or Git history.
- [ ] Confirm the actual deadline from the invitation: 48 hours after it was shared, not after this work started. Commits after that deadline will not count.
- [ ] With explicit approval, publish the allowed repository and verify signed-out access.
- [ ] Supply name, college, email, phone and repository URL in the assignment's submission form before the deadline. Use the form link in the original PDF.

## What the PDF does and does not say

Pages 5–7 require the checker, a one-page report (two maximum), the applicant's own `DECISIONS.md` (1½ pages maximum), a short README beginning with four specified lines, complete AI chats, genuine development commits and a three-minute recording. The PDF publishes no numerical scoring weights. Do not claim a guessed percentage for AI logs or code.

The PDF asks for a public repository but also says not to share the solution before the deadline. Confirm the intended publication timing with the organizer if the invitation does not resolve this tension. The raw pack remains private regardless of repository timing.
