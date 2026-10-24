#!/usr/bin/env python3
"""Build a self-contained, printable report from the same QC analysis as flags.csv.

Refuses stale flags. Only aggregated counts and findings enter the public report;
source timestamps and individual weather records remain in the private pack.
"""
import argparse
from html import escape
from pathlib import Path

import pandas as pd

from checker import analyze, coverage_summary


def choose_visit(result):
    ongoing = result.flags[(result.flags.action == 'exclude') &
                           (pd.to_datetime(result.flags.end_utc) >= result.end-pd.Timedelta(days=1))]
    wind = ongoing[ongoing.issue == 'Persistent wind scale change']
    heat = ongoing[ongoing.issue == 'Possible sunlight heating bias']
    if not wind.empty:
        station = wind.station_id.iloc[0]
        runner = heat.station_id.iloc[0] if not heat.empty else None
        return dict(station=station, runner=runner,
            reason='The wind change persists through the final day after a sensor replacement; verifying the model and logger conversion offers a focused, practical repair.',
            plan=[('0–10 min', 'Photograph the sensor model and logger settings; compare the documented pulse-to-speed conversion first.'),
                  ('10–40 min', 'Check wiring and free rotation; change the conversion only after confirming a mismatch, never from the peer ratio alone.'),
                  ('40–60 min', 'Verify against a reference or manufacturer-supported check, confirm live logging, and record settings, results and UTC intervention time.')],
            comparison=f'{runner} is second: its sunlight-linked warming needs a reference thermometer and exposure assessment; the cause and repair are less certain.' if runner else 'Review the remaining ongoing sensor faults after this targeted repair.')
    candidates = heat if not heat.empty else ongoing
    if not candidates.empty:
        station = candidates.station_id.iloc[0]
        return dict(station=station, runner=None,
                    reason='This station has an unresolved fault extending to the latest observations; verify the flagged sensor against an independent reference.',
                    plan=[('0–15 min', 'Record the sensor model, installation, logger settings and UTC time.'),
                          ('15–45 min', 'Compare the affected channel with an independent reference and inspect its mounting and connections.'),
                          ('45–60 min', 'Verify live logging and document the measured result before any calibration change.')],
                    comparison='Do not infer a calibration from neighboring stations alone.')
    return dict(station=None, runner=None, reason='No ongoing fault meets the implemented visit criteria.', plan=[], comparison='Review any metadata conflicts before assigning a visit.')


def report_html(result):
    coverage = coverage_summary(result)
    visit = choose_visit(result)
    columns = [('temp_c', 'Temp.'), ('rh_pct', 'Humidity'), ('pressure_hpa', 'Pressure'),
               ('wind_kmh', 'Wind'), ('wind_dir_deg', 'Direction'), ('rain_mm', 'Rain'), ('ghi_wm2', 'Sunlight')]
    table = []
    for station, counts in coverage.iterrows():
        values = []
        for channel, _ in columns:
            percent = 100*counts[channel]/counts.expected
            values.append(f'<td class="{"limited" if percent < 99.95 else ""}">{percent:.1f}%</td>')
        table.append(f'<tr><th scope="row">{escape(station)}</th>'+''.join(values)+'</tr>')
    def finding(issue):
        return result.flags[result.flags.issue.eq(issue)]
    evidence = []
    labels = {
        'GPS-proven clock offset': 'Clock recovered',
        'Persistent pressure step': 'Pressure withheld',
        'Sensor flatline': 'Temperature withheld',
        'Persistent humidity fault': 'Humidity withheld',
        'Blocked gauge / delayed release': 'Rain totals incomplete',
        'Persistent wind scale change': 'Wind withheld',
    }
    for issue, label in labels.items():
        found = finding(issue)
        if found.empty:
            continue
        f = found.iloc[0]
        if issue == 'GPS-proven clock offset':
            count = result.diagnostics[f.station_id].get('clock_corrected_rows', 0)
            detail = f'{count:,} time labels corrected using independent GPS; observations retained.'
        elif issue == 'Persistent pressure step':
            detail = f'Later pressure excluded from {pd.Timestamp(f.start_utc):%d %b %H:%M}; calibration is unverified.'
        elif issue == 'Sensor flatline':
            detail = f'Stuck from {pd.Timestamp(f.start_utc):%d %b %H:%M} to {pd.Timestamp(f.end_utc):%d %b %H:%M}; isolated spikes also removed.'
        elif issue == 'Persistent humidity fault':
            detail = f'{pd.Timestamp(f.start_utc):%d %b %H:%M}–{pd.Timestamp(f.end_utc):%d %b %H:%M}; prolonged overshoot exceeds ordinary saturation.'
        elif issue == 'Blocked gauge / delayed release':
            detail = 'Dry readings during peer rainfall and a later water release; withheld amounts are not reconstructed.'
        else:
            detail = f'Scale change from about {pd.Timestamp(f.start_utc):%d %b %H:%M}; check the sensor-to-logger conversion.'
        evidence.append(f'<li><b>{escape(f.station_id)} · {label}.</b> {escape(detail)}</li>')
    gaps = sum(i.get('missing_intervals', 0) for i in result.diagnostics.values())
    copies = sum(i.get('exact_duplicate_rows', 0) for i in result.diagnostics.values())
    raw = sum(i.get('input_rows', 0) for i in result.diagnostics.values())
    expected = int(coverage.expected.sum())
    heat = finding('Possible sunlight heating bias')
    uncertainty = []
    if not heat.empty:
        station = heat.station_id.iloc[0]
        onset = heat.start_utc.min()
        growth = result.diagnostics[station]['exposure']['bright_dark_growth_c']
        uncertainty.append(f'{station}: daytime warming against peers grew {growth:.1f}°C; strongly sunlit periods are withheld from {pd.Timestamp(onset):%d %b %H:%M}. Earlier onset is unclear: defer full-window temperature maxima and trend claims.')
    conflicts = finding('Location sources disagree')
    if not conflicts.empty:
        uncertainty.append(f'{conflicts.station_id.iloc[0]}: GPS and installation coordinates disagree; retain weather provisionally and verify location before mapping it.')
    # Keep the title specific without assuming station IDs or the pack length.
    title = f'Send the technician to {visit["station"]}.' if visit['station'] else 'Weather network: what to use and what to check'
    station_name = escape(str(result.stations.loc[visit['station'], 'name'])) if visit['station'] else 'No visit selected'
    plan = ''.join(f'<li><b>{escape(time)}</b> {escape(text)}</li>' for time, text in visit['plan'])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Network health · {result.start:%d %b}–{result.end:%d %b %Y}</title>
<style>
@page {{size:A4; margin:11mm 13mm;}}
* {{box-sizing:border-box}} body {{font:10pt/1.28 Arial,Helvetica,sans-serif;color:#182126;margin:0;background:white}}
main {{max-width:184mm;margin:0 auto}} .eyebrow {{font-size:8pt;letter-spacing:.12em;text-transform:uppercase;font-weight:700}}
header {{border-top:4px solid #182126;padding-top:8px;margin-bottom:10px}} h1 {{font-size:25pt;line-height:1.08;letter-spacing:-.035em;margin:7px 0}}
.period {{margin:0;color:#404a50}} .lead {{font-size:10pt;margin:8px 0 0;max-width:170mm}}
.counts {{display:flex;gap:24px;padding:9px 0;border-top:1px solid #b0b6ba;border-bottom:1px solid #b0b6ba;margin-bottom:13px}}
.counts b {{font-size:16pt;display:block}} .counts span {{font-size:8pt}}
h2 {{font-size:12pt;margin:10px 0 6px}} p {{margin:5px 0}} table {{border-collapse:collapse;width:100%;font-size:9pt;line-height:1.2;font-variant-numeric:tabular-nums}}
th,td {{padding:3px 5px;text-align:right;border-bottom:1px solid #d9dddf}} thead th {{font-size:8pt;border-bottom:2px solid #49545a}} th:first-child {{text-align:left}}
.limited {{font-weight:700;background:#edf0f1}} .caption {{font-size:8pt;color:#404a50;margin-top:6px}}
.evidence {{columns:2;column-gap:20px;padding-left:15px;font-size:8.7pt;line-height:1.25;margin:7px 0}}
.evidence li {{break-inside:avoid;margin-bottom:6px;padding-left:1px}} .visit {{border:1.5px solid #182126;padding:9px 12px;margin-top:12px;break-inside:avoid}}
.visit h2 {{margin-top:0}} .visit p,.visit li {{font-size:9pt}} .visit ol {{padding-left:17px;margin:6px 0}} .visit li {{margin:4px 0}}
.uncertain {{font-size:8.5pt;margin-top:10px}} .uncertain h2 {{font-size:10pt}} footer {{border-top:1px solid #b0b6ba;margin-top:10px;padding-top:5px;font-size:7.5pt;color:#404a50}}
@media screen {{body {{background:#e7e9ea;padding:24px}} main {{background:white;max-width:210mm;padding:12mm 13mm;box-shadow:0 2px 12px #0002}}}}
@media print {{body {{print-color-adjust:exact;-webkit-print-color-adjust:exact}}}}
</style></head><body><main>
<header><div class="eyebrow">Network health / coordinator's decision sheet</div>
<h1>{escape(title)}</h1><p class="period">{len(result.stations)} stations · {result.start:%d %B}–{result.end:%d %B %Y} · all times UTC</p>
<p class="lead">Use observations by sensor and interval. Keep independently corroborated weather extremes; withhold the faulty periods listed in <b>flags.csv</b>.</p></header>
<div class="counts"><div><b>{raw:,}</b><span>source records examined</span></div><div><b>{gaps:,}</b><span>scheduled intervals missing</span></div><div><b>{copies:,}</b><span>replayed copies removed</span></div><div><b>{len(result.flags)}</b><span>issue / retained-event intervals</span></div></div>
<h2>Data available for this summary</h2>
<table aria-label="Usable coverage by station and channel"><thead><tr><th>Station</th>{''.join('<th>'+label+'</th>' for _, label in columns)}</tr></thead><tbody>{''.join(table)}</tbody></table>
<p class="caption">Scheduled intervals remaining after corrections, duplicate removal and exclusions; shaded cells have incomplete coverage ({expected:,} station-intervals expected). Report coverage alongside each channel's summary.</p>
<h2>What changes the summary</h2><ul class="evidence">{''.join(evidence)}</ul>
<p class="caption">Do not treat gaps as zero rain or extrapolate an incomplete rain total into a complete one. Localized extremes can be real; the checker retains multi-station warm, dry, windy episodes.</p>
<section class="visit"><h2>Send the technician to {escape(visit['station'] or 'manual review')} · {station_name}</h2>
<p>{escape(visit['reason'])}</p><ol>{plan}</ol><p><b>Why this visit first:</b> {escape(visit['comparison'])}</p></section>
<section class="uncertain"><h2>Calls that still need judgment</h2>{''.join('<p>'+escape(x)+'</p>' for x in uncertainty)}</section>
<footer>Coverage measures availability under these checks; calibration and snow capture remain unverified. Report the observation window with each summary. See flags.csv for interval evidence.</footer>
</main></body></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack', type=Path)
    args = parser.parse_args(argv)
    try:
        result = analyze(args.pack)
        existing = pd.read_csv('flags.csv', dtype=str).fillna('')
        if not existing.equals(result.flags.astype(str)):
            raise ValueError('flags.csv does not match current checker results; run checker.py first')
        Path('report.html').write_text(report_html(result), encoding='utf-8')
        coverage_summary(result).to_csv('coverage.csv')
        print('Wrote report.html and coverage.csv from matching flags.csv.')
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        parser.exit(2, f'report: {exc}\n')


if __name__ == '__main__':
    main()
