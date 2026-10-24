#!/usr/bin/env python3
"""Conservative weather-pack QC; source files are never edited.

Order matters: validate GPS, resolve proven clock epochs in SOURCE order, remove
exact replay copies, then compare sensors. Spatial disagreement alone is not a
fault: comparisons use changes in each station's own peer residual, not equality
with a neighbor. Thresholds and unresolved cases are documented in README.md.

The public output contains problem intervals, not replacement observations.
Optional diagnostics contain source row identities and MUST remain private.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

CHANNELS = ['temp_c', 'rh_pct', 'pressure_hpa', 'wind_kmh',
            'wind_dir_deg', 'rain_mm', 'ghi_wm2']
FIELDS = ['station_id', 'channel', 'start_utc', 'end_utc', 'issue', 'action', 'note']
TIME_FORMAT = '%Y-%m-%d %H:%M'


def distance_km(lat1, lon1, lat2, lon2):
    a, b = np.radians([lat1, lat2])
    dlat, dlon = np.radians([lat2 - lat1, lon2 - lon1])
    h = np.sin(dlat / 2)**2 + np.cos(a) * np.cos(b) * np.sin(dlon / 2)**2
    return float(6371 * 2 * np.arcsin(np.sqrt(np.clip(h, 0, 1))))


def coordinate(value: str, hemisphere: str, latitude: bool) -> float:
    allowed = ('N', 'S') if latitude else ('E', 'W')
    pattern = r'\d{4}(?:\.\d+)?' if latitude else r'\d{5}(?:\.\d+)?'
    if hemisphere not in allowed or not re.fullmatch(pattern, value):
        raise ValueError('invalid coordinate format')
    number = float(value)
    degrees, minutes = divmod(number, 100)
    result = degrees + minutes / 60
    if minutes >= 60 or result > (90 if latitude else 180):
        raise ValueError('coordinate out of range')
    return -result if hemisphere in ('S', 'W') else result


def parse_gps(path: Path):
    """Trust only checked, active RMC fixes; validate understood GGA fields too.

    GGA has no date, so it is never independently used to correct a clock.
    Rejected sentences remain diagnostic counts, not automatic weather failures.
    """
    fixes, heights, rejected = [], [], []
    if not path.exists():
        return pd.DataFrame(), heights, [{'source_row': 0, 'reason': 'missing file'}]
    for row, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        try:
            stamp, sentence = line.split(',', 1)
            logger = datetime.strptime(stamp, '%Y-%m-%d %H:%M:%S')
            if not sentence.startswith('$') or '*' not in sentence:
                raise ValueError('missing checksum or sentence marker')
            body, checksum = sentence[1:].split('*')
            expected = 0
            for char in body:
                expected ^= ord(char)
            if not re.fullmatch('[0-9A-Fa-f]{2}', checksum) or expected != int(checksum, 16):
                raise ValueError('bad checksum')
            fields = body.split(',')
            kind = fields[0][-3:]
            if kind not in ('RMC', 'GGA'):
                raise ValueError('unsupported sentence')
            if kind == 'RMC':
                if len(fields) < 10:
                    raise ValueError('short RMC')
                if fields[2] != 'A':
                    raise ValueError('void fix')
                if not re.fullmatch(r'\d{6}(?:\.\d+)?', fields[1]):
                    raise ValueError('invalid UTC time')
                if not re.fullmatch(r'\d{6}', fields[9]):
                    raise ValueError('invalid UTC date')
                utc = datetime.strptime(fields[9] + fields[1].split('.')[0], '%d%m%y%H%M%S')
                lat = coordinate(fields[3], fields[4], True)
                lon = coordinate(fields[5], fields[6], False)
                fixes.append(dict(source_row=row, logger_time=pd.Timestamp(logger),
                                  gps_utc=pd.Timestamp(utc), lat=lat, lon=lon,
                                  correction_min=int(round((utc - logger).total_seconds() / 60))))
            else:
                if len(fields) < 15:
                    raise ValueError('short GGA')
                if fields[6] not in ('1', '2', '3', '4', '5'):
                    raise ValueError('invalid GGA fix quality')
                datetime.strptime(fields[1].split('.')[0], '%H%M%S')
                coordinate(fields[2], fields[3], True)
                coordinate(fields[4], fields[5], False)
                altitude, hdop = float(fields[9]), float(fields[8])
                if fields[10] != 'M' or not math.isfinite(altitude) or not math.isfinite(hdop) or hdop < 0:
                    raise ValueError('invalid GGA height or precision')
                if not 1 <= int(fields[7]) <= 99:
                    raise ValueError('invalid satellite count')
                heights.append(altitude)
        except (ValueError, IndexError, OverflowError) as exc:
            rejected.append(dict(source_row=row, reason=str(exc)))
    return pd.DataFrame(fixes), heights, rejected


def periods(times, mask, interval):
    """Inclusive sample-end bounds; never bridge missing observations."""
    times = pd.Series(times).reset_index(drop=True)
    mask = pd.Series(np.asarray(mask, dtype=bool))
    if times.empty:
        return
    group = ((mask != mask.shift(fill_value=False)) |
             (times.diff() != interval)).cumsum()
    for _, selected in times[mask].groupby(group[mask]):
        yield selected.iloc[0], selected.iloc[-1], selected.index.to_numpy()


@dataclass
class Analysis:
    flags: pd.DataFrame
    frames: dict
    stations: pd.DataFrame
    diagnostics: dict
    start: pd.Timestamp
    end: pd.Timestamp


class Checker:
    def __init__(self, pack):
        self.pack = Path(pack)
        self.rows = []
        self.frames = {}
        self.diagnostics = {}
        self.notes = []

    def add(self, station, channel, start, end, issue, action, note):
        self.rows.append(dict(zip(FIELDS, [str(station), channel,
                         pd.Timestamp(start).strftime(TIME_FORMAT),
                         pd.Timestamp(end).strftime(TIME_FORMAT), issue, action, note])))

    def flag_mask(self, station, channel, mask, issue, action, note):
        frame = self.frames[station]
        for start, end, indices in periods(frame._time, mask, self.intervals[station]):
            self.add(station, channel, start, end, issue, action,
                     note(indices) if callable(note) else note)

    def excluded(self, station, channel):
        d = self.frames[station]
        mask = pd.Series(False, index=d.index)
        for f in self.rows:
            if f['station_id'] == station and f['action'] == 'exclude' and f['channel'] in (channel, 'all'):
                mask |= d._time.between(pd.Timestamp(f['start_utc']), pd.Timestamp(f['end_utc']))
        return mask

    def maintenance(self, station, words, start, end):
        """Dates corroborate; unspecified local note times never set UTC bounds."""
        lo, hi = pd.Timestamp(start).normalize() - pd.Timedelta(days=1), pd.Timestamp(end).normalize() + pd.Timedelta(days=1)
        return [date for date, sid, text in self.notes if sid == station and lo <= date <= hi
                and any(word in text.lower() for word in words)]

    def read(self):
        path = self.pack / 'stations.csv'
        if not path.exists():
            raise ValueError(f'missing metadata file: {path}')
        meta = pd.read_csv(path, dtype={'station_id': str})
        needed = ['station_id', 'name', 'lat', 'lon', 'elevation_m', 'logger_interval_min']
        missing = set(needed) - set(meta)
        if missing:
            raise ValueError(f'stations.csv missing columns: {", ".join(sorted(missing))}')
        if meta.empty or meta.station_id.isna().any() or meta.station_id.duplicated().any():
            raise ValueError('stations.csv needs unique, nonempty station IDs')
        if not meta.station_id.map(lambda x: bool(re.fullmatch(r'[A-Za-z0-9_-]+', x))).all():
            raise ValueError('station IDs must be safe file names (letters, numbers, underscore, hyphen)')
        for c in ['lat', 'lon', 'elevation_m', 'logger_interval_min']:
            meta[c] = pd.to_numeric(meta[c], errors='coerce')
            if not np.isfinite(meta[c]).all():
                raise ValueError(f'invalid numeric metadata: {c}')
        if not (meta.lat.between(-90, 90).all() and meta.lon.between(-180, 180).all()
                and meta.logger_interval_min.between(1, 1440).all()
                and meta.logger_interval_min.mod(1).eq(0).all()):
            raise ValueError('metadata coordinates or logging intervals out of range')
        self.stations = meta.set_index('station_id').sort_index()
        self.intervals = {s: pd.Timedelta(minutes=int(m.logger_interval_min)) for s, m in self.stations.iterrows()}
        notes_path = self.pack / 'maintenance_log.md'
        if notes_path.exists():
            for line in notes_path.read_text().splitlines():
                match = re.match(r'(\d{4}-\d{2}-\d{2})\s+(\S+)\s+(.*)', line)
                if match:
                    date = pd.to_datetime(match[1], errors='coerce')
                    if not pd.isna(date):
                        self.notes.append((date, match[2], match[3]))
        failed = {}
        for station in self.stations.index:
            path = self.pack / 'data' / f'{station}.csv'
            try:
                d = pd.read_csv(path, keep_default_na=True)
                missing = set(['timestamp_utc', *CHANNELS]) - set(d)
                if missing:
                    raise ValueError(f'missing columns: {", ".join(sorted(missing))}')
                d['_source_row'] = np.arange(len(d)) + 2
                d['_raw_timestamp'] = d.timestamp_utc.astype(str)
                exact = d._raw_timestamp.str.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}')
                d['_time'] = pd.to_datetime(d._raw_timestamp.where(exact), format=TIME_FORMAT, errors='coerce')
                invalid = d._time.isna()
                info = dict(input_rows=len(d), invalid_timestamp_rows=d.loc[invalid, '_source_row'].tolist(),
                            invalid_numeric={}, warnings=[])
                d = d[~invalid].copy().reset_index(drop=True)
                if d.empty:
                    raise ValueError('no valid timestamps')
                for channel in CHANNELS:
                    values = pd.to_numeric(d[channel], errors='coerce')
                    invalid = ~np.isfinite(values)
                    info['invalid_numeric'][channel] = d.loc[invalid, '_source_row'].tolist()
                    d[channel] = values.where(~invalid)
                self.frames[station] = d
                self.diagnostics[station] = info
            except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
                failed[station] = str(exc)
        if not self.frames:
            raise ValueError('no readable weather files: ' + '; '.join(f'{s}: {e}' for s, e in failed.items()))
        # Temporary bounds are replaced by corrected bounds after GPS processing.
        self.start = min(d._time.min() for d in self.frames.values())
        self.end = max(d._time.max() for d in self.frames.values())
        self.failed = failed

    def clocks(self):
        for station, d in self.frames.items():
            fixes, heights, rejected = parse_gps(self.pack / 'gps' / f'{station}.nmea')
            info = self.diagnostics[station]
            info['gps'] = dict(trusted_rmc=len(fixes), rejected=dict(Counter(x['reason'] for x in rejected)),
                               rejected_rows=rejected, median_height_m=float(np.median(heights)) if heights else None)
            if fixes.empty:
                self.add(station, 'metadata', d._time.min(), d._time.max(), 'GPS unavailable', 'keep',
                         'No validated active RMC fixes are available, so weather values are retained but GPS cannot verify their clock or location.')
                continue
            groups = fixes.correction_min.ne(fixes.correction_min.shift()).cumsum()
            epochs = [g for _, g in fixes.groupby(groups) if len(g) >= 3 and
                      (g.gps_utc.max() - g.gps_utc.min()) >= pd.Timedelta(hours=2)]
            if not epochs and fixes.correction_min.ne(0).all():
                info['warnings'].append('nonzero GPS offsets lack three fixes spanning two hours')
            shifts = pd.Series(0, index=d.index, dtype='int64')
            previous = None
            for epoch in epochs:
                shift = int(epoch.correction_min.iloc[0])
                if abs(shift) > 24 * 60:
                    info['warnings'].append('GPS offset exceeds one day; correction refused')
                    continue
                if previous is None:
                    if abs((epoch.gps_utc.iloc[0] - (d._time.iloc[0] + pd.Timedelta(minutes=shift))).total_seconds()) > 7200:
                        info['warnings'].append('initial GPS epoch does not bracket start; correction refused')
                        continue
                    start_index = 0
                else:
                    old_shift = int(previous.correction_min.iloc[0])
                    if shift == old_shift:
                        previous = epoch
                        continue
                    expected_delta = self.intervals[station] - pd.Timedelta(minutes=shift - old_shift)
                    candidates = d.index[d._time.diff().eq(expected_delta)]
                    candidates = [i for i in candidates if previous.gps_utc.iloc[-1] <=
                                  d._time.iloc[i] + pd.Timedelta(minutes=shift) <= epoch.gps_utc.iloc[0]]
                    if len(candidates) != 1:
                        info['warnings'].append('GPS offset transition has no unique weather-row boundary; correction refused')
                        continue
                    start_index = candidates[0]
                shifts.iloc[start_index:] = shift
                previous = epoch
            d['_time'] += pd.to_timedelta(shifts, unit='m')
            for start, end, indices in periods(d._time, shifts.ne(0), self.intervals[station]):
                # Separate distinct correction amounts even if epochs are adjacent.
                for correction in sorted(shifts.iloc[indices].unique()):
                    chosen = indices[shifts.iloc[indices].to_numpy() == correction]
                    if len(chosen):
                        rows = d._source_row.iloc[chosen]
                        self.add(station, 'timestamp_utc', d._time.iloc[chosen[0]], d._time.iloc[chosen[-1]],
                                 'GPS-proven clock offset', 'correct',
                                 f'Add {int(correction):+d} minutes to original CSV rows {rows.min()}–{rows.max()} using persistent valid RMC UTC offsets and the matching logger discontinuity; bounds here are corrected UTC.')
            info['clock_corrected_rows'] = int(shifts.ne(0).sum())
            info['gps']['offset_counts'] = {str(int(k)): int(v) for k, v in fixes.correction_min.value_counts().items()}
            if info['warnings']:
                self.add(station, 'all', d._time.min(), d._time.max(), 'Unresolved clock evidence', 'exclude',
                         'GPS clock evidence cannot be mapped uniquely to weather source rows, so this station requires manual timestamp review before use.')
            if len(fixes) >= 12:
                lat, lon = fixes[['lat', 'lon']].median()
                spread = max(distance_km(lat, lon, a, b) for a, b in fixes[['lat', 'lon']].itertuples(index=False, name=None))
                m = self.stations.loc[station]
                separation = distance_km(lat, lon, m.lat, m.lon)
                info['gps']['location_separation_km'] = round(separation, 3)
                if separation > 1 and spread < .1:
                    self.add(station, 'metadata', d._time.min(), d._time.max(), 'Location sources disagree', 'keep',
                             f'{len(fixes)} validated GPS fixes cluster {separation:.1f} km from the installation coordinates; retain weather provisionally and verify both location sources before spatial attribution.')

    def integrity(self):
        self.start = min(d._time.min() for d in self.frames.values())
        self.end = max(d._time.max() for d in self.frames.values())
        if self.end - self.start > pd.Timedelta(days=3660):
            raise ValueError('pack spans more than ten years; inspect timestamp parsing before expanding a time grid')
        for station, error in self.failed.items():
            self.add(station, 'all', self.start, self.end, 'Unreadable weather file', 'exclude',
                     f'The weather file cannot be used: {error.replace(chr(10), " ")}.')
            expected = len(pd.date_range(self.start, self.end, freq=self.intervals[station]))
            self.diagnostics[station] = dict(error=error, expected_intervals=expected, missing_intervals=expected)
        for station, d in list(self.frames.items()):
            interval = self.intervals[station]
            info = self.diagnostics[station]
            if info['invalid_timestamp_rows']:
                self.add(station, 'metadata', self.start, self.end, 'Untimed source rows', 'keep',
                         f'{len(info["invalid_timestamp_rows"])} rows have invalid UTC labels and are omitted; valid timed observations are retained and any resulting gaps are listed separately.')
            duplicate = d.duplicated(['_time', *CHANNELS], keep='first')
            info['exact_duplicate_rows'] = int(duplicate.sum())
            if duplicate.any():
                copies = d.loc[duplicate].sort_values('_time', kind='stable')
                for start, end, indices in periods(copies._time, np.ones(len(copies), bool), interval):
                    self.add(station, 'all', start, end, 'Exact record replay', 'correct',
                             f'Drop {len(indices)} later exact copies only and retain the first copy at each time; every weather channel matches the earlier records.')
            d['_duplicate_copy'] = duplicate
            info['source_timestamps'] = d[['_source_row', '_raw_timestamp', '_time', '_duplicate_copy']].copy()
            retained = d[~duplicate]
            backward = retained._time.diff().lt(-interval)
            if backward.any():
                # Replay copies are already gone, and proved clock epochs are
                # already corrected. Never quietly accept a still-shifted tail.
                first = np.flatnonzero(backward.to_numpy())[0]
                unresolved_start = retained._time.iloc[first:].min()
                self.add(station, 'all', unresolved_start, self.end, 'Unresolved backward sequence', 'exclude',
                         'After removing exact replay copies, the source sequence still jumps backward without a proven clock repair; withhold the ambiguous later timeline pending source-order review.')
            d = retained.sort_values(['_time', '_source_row'], kind='stable').reset_index(drop=True)
            self.frames[station] = d
            conflicts = d._time.duplicated(keep=False) & ~self.excluded(station, 'temp_c')
            self.flag_mask(station, 'all', conflicts, 'Conflicting repeated time', 'exclude',
                           'Different source records share this UTC label without a GPS-proven correction; neither copy can be assigned reliably to an interval.')
            grid = pd.date_range(self.start, self.end, freq=interval)
            missing = grid.difference(d._time)
            info['expected_intervals'] = len(grid)
            info['missing_intervals'] = len(missing)
            for start, end, indices in periods(missing, np.ones(len(missing), bool), interval):
                self.add(station, 'all', start, end, 'Missing observations', 'exclude',
                         f'{len(indices)} expected {interval.total_seconds()/60:g}-minute observations are absent from the shared pack window; no values are imputed.')
            off_grid = ~d._time.isin(grid)
            self.flag_mask(station, 'all', off_grid, 'Off-schedule timestamp', 'exclude',
                           'The UTC label does not fall on the documented sampling grid; retain its source identity for manual review.')
            for channel, rows in info['invalid_numeric'].items():
                self.flag_mask(station, channel, d._source_row.isin(rows), 'Invalid numeric value', 'exclude',
                               'This value is missing, non-numeric or non-finite in the documented numeric channel.')

    def local_sensors(self):
        # Broad bounds are screening limits for these units, not climatological normals.
        bounds = dict(temp_c=(-90, 60), rh_pct=(0, 103), pressure_hpa=(300, 1100),
                      wind_kmh=(0, 250), wind_dir_deg=(0, 360), ghi_wm2=(-5, 1600))
        for station, d in self.frames.items():
            minutes = self.intervals[station].total_seconds() / 60
            bounds_here = {**bounds, 'rain_mm': (0, 600 * minutes / 60)}
            # A near-saturated multi-day plateau with frequent overshoot is stronger
            # evidence than saturation itself, which can be genuine fog or rain.
            for start, end, ix in periods(d._time, d.rh_pct.ge(99), self.intervals[station]):
                v = d.rh_pct.iloc[ix]
                if len(ix) * minutes >= 12 * 60 and v.gt(100).mean() > .5 and v.max() > 103:
                    self.add(station, 'rh_pct', start, end, 'Persistent humidity fault', 'exclude',
                             f'{len(ix)} consecutive readings lie at {v.min():g}–{v.max():g}% with {int(v.gt(100).sum())} above 100%; this sustained overshoot is not ordinary saturation.')
            for channel, hours in [('temp_c', 6), ('pressure_hpa', 6), ('rh_pct', 12)]:
                v = d[channel].where(~self.excluded(station, channel))
                group = (v.ne(v.shift()) | d._time.diff().ne(self.intervals[station])).cumsum()
                for _, selected in d.groupby(group):
                    ix = selected.index
                    value = v.iloc[ix[0]]
                    if len(ix) * minutes >= hours * 60 and pd.notna(value) and not (channel == 'rh_pct' and value in (0, 100)):
                        self.add(station, channel, selected._time.iloc[0], selected._time.iloc[-1], 'Sensor flatline', 'exclude',
                                 f'{len(ix)} consecutive readings are exactly {value:g} over {len(ix)*minutes/60:g} hours of intervals while this channel should resolve natural variation.')
            # Isolated temperature/pressure excursions require return to the old level.
            for channel, threshold, return_tolerance in [('temp_c', 12, 2), ('pressure_hpa', 8, 2)]:
                v = d[channel].where(~self.excluded(station, channel))
                before, after = v.shift(), v.shift(-1)
                mask = ((v - before).abs().gt(threshold * max(1, np.sqrt(minutes / 10))) &
                        (v - after).abs().gt(threshold * max(1, np.sqrt(minutes / 10))) &
                        (before - after).abs().le(return_tolerance) &
                        d._time.diff().eq(self.intervals[station]) &
                        d._time.shift(-1).sub(d._time).eq(self.intervals[station]))
                self.flag_mask(station, channel, mask, 'Isolated sensor spike', 'exclude',
                               lambda ix, c=channel: f'{c} departs sharply for one interval and immediately returns within {return_tolerance:g} units of its preceding value; source rows {d._source_row.iloc[ix].min()}–{d._source_row.iloc[ix].max()} identify the excursion.')
            for channel, (low, high) in bounds_here.items():
                bad = (d[channel].lt(low) | d[channel].gt(high)) & ~self.excluded(station, channel)
                self.flag_mask(station, channel, bad, 'Outside screening bounds', 'exclude',
                               f'The documented {channel} value lies outside the broad screening range [{low:g}, {high:g}]; check units or sensor output before use.')
            overshoot = d.rh_pct.gt(100) & d.rh_pct.le(103) & ~self.excluded(station, 'rh_pct')
            self.flag_mask(station, 'rh_pct', overshoot, 'Minor humidity overshoot', 'keep',
                           'A small humidity overshoot of at most three percentage points can be sensor uncertainty near saturation; retain provisionally without clamping or treating it as a prolonged fault.')

    def peers(self, station):
        m = self.stations.loc[station]
        candidates = []
        for other in self.frames:
            if other == station:
                continue
            n = self.stations.loc[other]
            distance = distance_km(m.lat, m.lon, n.lat, n.lon)
            if distance <= 100 and abs(m.elevation_m - n.elevation_m) <= 700:
                candidates.append((distance + abs(m.elevation_m - n.elevation_m) / 100, other))
        return [s for _, s in sorted(candidates)[:4]]

    def wide(self, channel):
        values = {}
        for station, d in self.frames.items():
            valid = ~self.excluded(station, channel) & ~d._time.duplicated(keep=False)
            values[station] = pd.Series(d.loc[valid, channel].to_numpy(), index=d.loc[valid, '_time'])
        return pd.concat(values, axis=1, sort=True)

    def spatial(self):
        # Freeze locally validated references so station iteration order cannot
        # change which cross-station findings are generated.
        wide = {c: self.wide(c) for c in ['pressure_hpa', 'temp_c', 'ghi_wm2', 'rain_mm', 'rh_pct', 'wind_kmh']}
        for station, d in self.frames.items():
            peers = self.peers(station)
            self.diagnostics[station]['peers'] = peers
            if len(peers) < 2:
                continue
            refs = {c: v[peers].median(axis=1).where(v[peers].notna().sum(axis=1) >= 2)
                    for c, v in wide.items()}
            p = wide['pressure_hpa'][station]
            residual = p - refs['pressure_hpa']
            for time in p.index[p.diff().abs().ge(3)]:
                before = residual.loc[time-pd.Timedelta(days=1):time-self.intervals[station]].dropna()
                after = residual.loc[time:time+pd.Timedelta(days=1)].dropna()
                needed = max(3, math.ceil(180 / (self.intervals[station].total_seconds()/60)))
                if len(before) < needed or len(after) < needed:
                    continue
                change = after.median() - before.median()
                scatter = max((before - before.median()).abs().median(), (after - after.median()).abs().median())
                tail = residual.loc[time:].resample('D').median().dropna()
                persistent = ((tail - before.median()) * np.sign(change) > abs(change) * .6).mean()
                if abs(change) >= 4 and scatter <= 1.5 and persistent >= .8:
                    service = self.maintenance(station, ['pressure', 'board'], time, time)
                    self.add(station, 'pressure_hpa', time, d._time.max(), 'Persistent pressure step', 'exclude',
                             f'Pressure changes {p.diff().loc[time]:+.1f} hPa in one interval and its peer residual shifts {change:+.1f} hPa persistently' +
                             (' with a same-date board-service note' if service else '') +
                             '; withhold the later pressure segment because absolute calibration is unknown.')
                    break
            self.wind_change(station, wide['wind_kmh'], refs['wind_kmh'])
            self.exposure(station, wide, refs)
            self.rain_blockage(station, wide, peers)
            # Wind/solar zero runs need independent positive readings, unlike rain.
            for channel, hours, positive in [('wind_kmh', 24, 5), ('ghi_wm2', 48, 300)]:
                ref = refs[channel] if channel in refs else None
                for start, end, ix in periods(d._time, d[channel].eq(0), self.intervals[station]):
                    if len(ix) * self.intervals[station] >= pd.Timedelta(hours=hours):
                        evidence = ref.reindex(d._time.iloc[ix]).gt(positive).sum()
                        if evidence >= 12:
                            self.add(station, channel, start, end, 'Unresponsive zero sensor', 'exclude',
                                     f'This channel stays exactly zero for at least {hours} hours while at least two comparable stations support {evidence} nonzero intervals; inspect the sensor before use.')
        # A diagnosed faulty channel cannot corroborate a retained weather event.
        self.real_events({c: self.wide(c) for c in ['temp_c', 'rh_pct', 'wind_kmh']})

    def wind_change(self, station, wind, reference):
        daily = wind[station].resample('D').mean() / reference.resample('D').mean().replace(0, np.nan)
        needed = math.ceil(18 * 3600 / self.intervals[station].total_seconds())
        enough = wind[station].resample('D').count().ge(needed) & reference.resample('D').count().ge(needed)
        daily = daily.where(enough)
        daily = daily.replace([np.inf, -np.inf], np.nan).dropna()
        if len(daily) < 14:
            return
        choices = []
        for i in range(7, len(daily)-6):
            a, b = daily.iloc[:i], daily.iloc[i:]
            factor = b.median() / a.median() if a.median() > 0 else 1
            low, high = sorted([a.median(), b.median()])
            if (factor < .5 or factor > 2) and low > 0:
                stable = b.between(b.median()*.5, b.median()*1.5).mean()
                separated = min(a.gt(np.sqrt(low*high)).mean(), b.lt(np.sqrt(low*high)).mean()) if factor < 1 else min(a.lt(np.sqrt(low*high)).mean(), b.gt(np.sqrt(low*high)).mean())
                if stable >= .8 and separated >= .85:
                    choices.append((separated * abs(np.log(factor)), i, factor))
        if not choices:
            return
        _, split, factor = max(choices)
        boundary = daily.index[split]
        before_level = daily.iloc[:split].median()
        hourly = wind[station].resample('h').mean() / reference.resample('h').mean().replace(0, np.nan)
        low = hourly.lt(before_level*.5) if factor < 1 else hourly.gt(before_level*2)
        near = hourly.index.to_series().between(boundary-pd.Timedelta(hours=36), boundary+pd.Timedelta(hours=12))
        candidates = []
        for start, end, ix in periods(hourly.index, low & near.to_numpy(), pd.Timedelta(hours=1)):
            if len(ix) >= 6:
                candidates.append(start)
        start = min(candidates) if candidates else boundary
        d = self.frames[station]
        service = self.maintenance(station, ['anemometer', 'wind'], start-pd.Timedelta(days=1), start)
        self.add(station, 'wind_kmh', start, d._time.max(), 'Persistent wind scale change', 'exclude',
                 f'The daily wind-to-peer ratio changes by a factor of {factor:.2f} and stays separated for {len(daily)-split} days' +
                 (' around an anemometer replacement' if service else '') +
                 '; the onset is resolved to an hour and no hardware calibration factor is assumed.')

    def exposure(self, station, wide, refs):
        residual = wide['temp_c'][station] - refs['temp_c']
        light = wide['ghi_wm2'][station]
        a = pd.DataFrame(dict(residual=residual, light=light))
        bright = a[a.light.ge(500)].resample('D').residual.agg(['median', 'count'])
        dark = a[a.light.lt(10)].resample('D').residual.agg(['median', 'count'])
        minutes = self.intervals[station].total_seconds()/60
        daily = pd.DataFrame(dict(bright=bright['median'].where(bright['count'] >= math.ceil(120/minutes)),
                                  dark=dark['median'].where(dark['count'] >= math.ceil(240/minutes)))).dropna()
        if len(daily) < 21:
            return
        contrast = daily.bright - daily.dark
        baseline = contrast.iloc[:7].median()
        growth = contrast.iloc[-7:].median() - baseline
        night_change = daily.dark.iloc[-7:].median() - daily.dark.iloc[:7].median()
        slopes = [(contrast.iloc[j]-contrast.iloc[i]) / max(1, (contrast.index[j]-contrast.index[i]).days)
                  for i in range(len(contrast)) for j in range(i+1, len(contrast))]
        if growth < 2 or abs(night_change) > 1.5 or np.median(slopes) < .05:
            return
        smoothed = contrast.rolling(5, min_periods=5).median()
        candidate = smoothed[(smoothed > baseline+1.5) & (smoothed.index >= contrast.index[7])]
        if candidate.empty:
            return
        # Detection onset is deliberately conservative, not the date of a vague note.
        onset = candidate.index[0]
        d = self.frames[station]
        mask = d._time.ge(onset) & d.ghi_wm2.ge(500) & ~self.excluded(station, 'temp_c')
        self.diagnostics[station]['exposure'] = dict(bright_dark_growth_c=round(growth, 2),
                                                   night_change_c=round(night_change, 2), onset=str(onset))
        self.flag_mask(station, 'temp_c', mask, 'Possible sunlight heating bias', 'exclude',
                       f'The bright-minus-dark temperature residual against peers grows {growth:.1f}°C while the nighttime change is {night_change:+.1f}°C; conservatively withhold only these ≥500 W/m² intervals pending an exposure check, with onset uncertain.')

    def rain_blockage(self, station, wide, peers):
        d = self.frames[station]
        interval = self.intervals[station]
        for start, end, ix in periods(d._time, d.rain_mm.eq(0), interval):
            if len(ix) * interval < pd.Timedelta(days=2):
                continue
            next_rows = d.iloc[ix[-1]+1:ix[-1]+4]
            if next_rows.empty:
                release = 0
            else:
                release = next_rows.rain_mm.sum()
            rain = wide['rain_mm'].loc[start:end, peers]
            totals = rain.sum(min_count=1)
            wet_peers = totals[totals.ge(5)]
            service = self.maintenance(station, ['funnel', 'leaves', 'nest', 'clean', 'rain gauge'], end, end+pd.Timedelta(days=1))
            if len(wet_peers) < 2 or (release < 10 and not service):
                continue
            wet = rain[wet_peers.index].gt(0).sum(axis=1).ge(2)
            if not wet.any():
                continue
            first_wet = wet.index[wet][0]
            until = next_rows._time.iloc[-1] if release >= 10 else end
            self.add(station, 'rain_mm', first_wet, until, 'Blocked gauge / delayed release', 'exclude',
                     f'The gauge reports zero while {len(wet_peers)} peers each collect at least 5 mm, followed by {release:.1f} mm in three intervals' +
                     (' near a documented funnel cleaning' if service else '') +
                     '; onset is bracketed rather than exact and released water is neither timed rainfall nor safely redistributable.')

    def real_events(self, wide):
        temp, rh, wind = (wide[c].resample('h').median() for c in ['temp_c', 'rh_pct', 'wind_kmh'])
        # Compare the same UTC hour on preceding days, not daytime with nighttime.
        history = pd.concat([temp.shift(24*k) for k in range(1, 8)], keys=range(7)).groupby(level=1).median()
        unusual = (temp-history).ge(8) & rh.lt(25) & wind.ge(15)
        coherent = unusual.sum(axis=1).ge(3)
        for station in sorted(self.frames):
            d = self.frames[station]
            for start, end, ix in periods(temp.index, coherent & unusual[station], pd.Timedelta(hours=1)):
                if len(ix) < 2:
                    continue
                # A keep event must not overlap an excluded channel's bad interval.
                mask = d._time.between(start, end+pd.Timedelta(minutes=59))
                if any((mask & self.excluded(station, c)).any() for c in ['temp_c', 'rh_pct', 'wind_kmh']):
                    continue
                self.flag_mask(station, 'temp_c', mask & ~self.excluded(station, 'temp_c'),
                               'Coherent warm dry windy event', 'keep',
                               'For at least two hours, three or more stations independently show ≥8°C warming against the same UTC hours of preceding days with humidity <25% and wind ≥15 km/h; retain this corroborated temperature event.')

    def run(self):
        self.read()
        self.clocks()
        self.integrity()
        self.local_sensors()
        self.spatial()
        flags = pd.DataFrame(self.rows, columns=FIELDS).drop_duplicates()
        flags = flags.sort_values(['station_id', 'start_utc', 'channel', 'issue', 'end_utc'], kind='stable').reset_index(drop=True)
        return Analysis(flags, self.frames, self.stations, self.diagnostics, self.start, self.end)


def analyze(pack):
    return Checker(pack).run()


def usable_mask(result, station, channel):
    """Coverage counts available, finite, unexcluded records, never replay copies."""
    d = result.frames[station]
    valid = d[channel].notna() & ~d._time.duplicated(keep=False)
    for f in result.flags.itertuples(index=False):
        if f.station_id == station and f.action == 'exclude' and f.channel in (channel, 'all'):
            valid &= ~d._time.between(pd.Timestamp(f.start_utc), pd.Timestamp(f.end_utc))
    return valid


def coverage_summary(result):
    rows = []
    for station, m in result.stations.iterrows():
        expected = len(pd.date_range(result.start, result.end, freq=pd.Timedelta(minutes=int(m.logger_interval_min))))
        row = dict(station_id=station, expected=expected)
        for channel in CHANNELS:
            row[channel] = int(usable_mask(result, station, channel).sum()) if station in result.frames else 0
        rows.append(row)
    return pd.DataFrame(rows).set_index('station_id')


def write_diagnostics(result, path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    summary = {}
    for station, info in result.diagnostics.items():
        summary[station] = {k: v for k, v in info.items() if k != 'source_timestamps'}
        if 'source_timestamps' in info:
            info['source_timestamps'].to_csv(path / f'{station}_timestamps_PRIVATE.csv', index=False)
    (path / 'summary_PRIVATE.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pack', type=Path, help='folder containing stations.csv, data/, gps/ and maintenance_log.md')
    parser.add_argument('--diagnostics', type=Path, help='PRIVATE output directory for source-row timestamp audits; never commit it')
    args = parser.parse_args(argv)
    try:
        result = analyze(args.pack)
        result.flags.to_csv(Path.cwd() / 'flags.csv', index=False)
        if args.diagnostics:
            write_diagnostics(result, args.diagnostics)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        print(f'checker: {exc}', file=sys.stderr)
        return 2
    print(f'Wrote flags.csv: {len(result.flags)} problem/event intervals across {len(result.stations)} stations.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
