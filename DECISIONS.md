# Decisions — author worksheet (not ready to submit)

Replace these prompts with your own words and keep the finished document within 1½ pages. The report contains an evidence-based recommendation; this worksheet does not claim your personal reasoning or field observations.

## 1. The visit

**Your answer:** [Choose the station, specify the first check and the one-hour plan, and explain why it beats your second choice.]

Evidence to inspect: S07's wind change near 26 March, the anemometer replacement note, its flag, and `report.html`. The checker finds a persistent wind-to-peer ratio change of about 0.25; that ratio is evidence of a problem, not a calibration factor. Compare S04's sunlight-linked temperature drift and the uncertainty of its cause. Say which equipment the technician must bring.

## 2. Your least certain call

**Your answer:** [Select an actual flag; give evidence for and against it, then name one observation or record that would settle it.]

Candidate: S04's `Possible sunlight heating bias`. Its bright-versus-dark peer residual grows about 3.5°C while the nighttime change is about −0.25°C. Exposure changes are plausible, but local weather, peer selection and the onset remain uncertain. The automatic threshold first excludes strongly sunlit periods on 1 April; it does not establish when the bias began. Consider what a simultaneous independent temperature measurement would tell you. Alternatively, investigate S05's GPS/install-location conflict.

## 3. Where AI was wrong

**Your answer:** [Copy one or two short, exact quotes from your complete AI chat export; explain what you checked and how you found each error.]

Actual development records worth inspecting: the first synthetic “normal pack” used different metadata latitudes but identical GPS coordinates, so its no-false-alarm test failed; the fixture was corrected. Also, the first event-retention implementation used channel `all`, which could conflict with a separate pressure exclusion; it was narrowed to `temp_c`. Verify the original code/quotes in the chat before describing either example. Do not invent a quote or claim you personally discovered something you did not check.

## 4. Next year: 500 stations

**Your answer:** [What must change, what would you drop, and which decisions would still require a person?]

Consider state across runs, validated sensor/model metadata, processing time, reliable peer selection, prioritizing actionable alerts, and distinguishing missing communications from missing measurements. The current checker loads a complete pack and has no operational alerting history. Decide whether routine retained-event flags deserve an alert and who can approve a calibration or resolve conflicting locations.

## 5. By hand — leave AI out of this calculation

**Your working:** [Without code or AI, estimate the UTC time of the Sun's highest point at S04 on 20 March 2025; show a few lines and explain its relevance.]

Read S04's coordinates directly from your private `stations.csv`. Write the estimate yourself. No answer, formula or computed time has been supplied here.
