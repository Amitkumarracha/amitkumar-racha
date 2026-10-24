from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from checker import FIELDS, TIME_FORMAT, analyze, coordinate, parse_gps, write_diagnostics, coverage_summary


def sentence(body):
    check = 0
    for char in body:
        check ^= ord(char)
    return f'${body}*{check:02X}'


def rmc(time, logger=None, status='A', latitude='4000.0000'):
    logger = time if logger is None else logger
    body = f'GPRMC,{time:%H%M%S}.00,{status},{latitude},N,10500.0000,W,0.0,0.0,{time:%d%m%y},,,A'
    return f'{logger:%Y-%m-%d %H:%M:%S},' + sentence(body)


def pack(tmp_path, ids=('WX9',), n=288, start='2031-06-01', reset=None):
    (tmp_path / 'data').mkdir()
    (tmp_path / 'gps').mkdir()
    times = pd.date_range(start, periods=n, freq='10min')
    meta = []
    for j, station in enumerate(ids):
        phase = np.arange(n)*2*np.pi/144
        data = pd.DataFrame(dict(timestamp_utc=times.strftime(TIME_FORMAT),
            temp_c=10 + j*.2 + 5*np.sin(phase), rh_pct=60-15*np.sin(phase),
            pressure_hpa=850+j+3*np.sin(phase/3), wind_kmh=9+3*np.sin(phase),
            wind_dir_deg=(180+30*np.sin(phase)).round(), rain_mm=np.zeros(n),
            ghi_wm2=np.maximum(0, 800*np.sin(phase))))
        data.to_csv(tmp_path/'data'/f'{station}.csv', index=False)
        gps = []
        for i in range(0, n, 6):
            shift = reset[1] if reset and i >= reset[0] else 0
            gps.append(rmc(times[i], times[i]-pd.Timedelta(minutes=shift), latitude=f'{4000+j*.6:09.4f}'))
        (tmp_path/'gps'/f'{station}.nmea').write_text('\n'.join(gps)+'\n')
        meta.append(dict(station_id=station, name=f'Station {station}', lat=40+j*.01,
                         lon=-105, elevation_m=1500+j*10, logger_interval_min=10))
    pd.DataFrame(meta).to_csv(tmp_path/'stations.csv', index=False)
    (tmp_path/'maintenance_log.md').write_text('# No recorded maintenance\n')
    return times


def change(tmp_path, station, fn):
    path = tmp_path/'data'/f'{station}.csv'
    d = pd.read_csv(path)
    value = fn(d)
    (d if value is None else value).to_csv(path, index=False)


def issues(result, name):
    return result.flags[result.flags.issue.eq(name)]


@pytest.mark.parametrize('n', [288, 144*35])
def test_normal_pack_has_no_flags(tmp_path, n):
    pack(tmp_path, ids=('AA', 'BB', 'CC'), n=n)
    assert analyze(tmp_path).flags.empty


def test_missing_intervals_and_off_grid(tmp_path):
    times = pack(tmp_path)
    def edit(d):
        d = d.drop([10, 11])
        d.loc[20, 'timestamp_utc'] = '2031-06-01 03:25'
        return d
    change(tmp_path, 'WX9', edit)
    result = analyze(tmp_path)
    gaps = issues(result, 'Missing observations')
    assert gaps.iloc[0].start_utc == times[10].strftime(TIME_FORMAT)
    assert gaps.iloc[0].end_utc == times[11].strftime(TIME_FORMAT)
    assert len(issues(result, 'Off-schedule timestamp')) == 1


def test_replay_drops_only_later_exact_copies(tmp_path):
    pack(tmp_path)
    change(tmp_path, 'WX9', lambda d: pd.concat([d, d.iloc[20:32]], ignore_index=True))
    result = analyze(tmp_path)
    assert len(result.frames['WX9']) == 288
    flags = issues(result, 'Exact record replay')
    assert len(flags) == 1 and flags.iloc[0].action == 'correct'
    assert result.diagnostics['WX9']['exact_duplicate_rows'] == 12
    assert issues(result, 'GPS-proven clock offset').empty


def test_clock_reset_preserves_all_measurements_and_source_order(tmp_path):
    times = pack(tmp_path, reset=(144, 360))
    def edit(d):
        d.loc[144:, 'timestamp_utc'] = (times[144:]-pd.Timedelta(hours=6)).strftime(TIME_FORMAT)
    change(tmp_path, 'WX9', edit)
    result = analyze(tmp_path)
    d = result.frames['WX9']
    assert len(d) == len(times) and d._time.nunique() == len(times)
    assert d._time.tolist() == times.tolist()
    assert d._source_row.tolist() == list(range(2, 290))
    f = issues(result, 'GPS-proven clock offset').iloc[0]
    assert f.start_utc == times[144].strftime(TIME_FORMAT)
    assert '+360' in f.note
    assert issues(result, 'Exact record replay').empty
    assert issues(result, 'Missing observations').empty
    write_diagnostics(result, tmp_path/'private_audit')
    audit = pd.read_csv(tmp_path/'private_audit'/'WX9_timestamps_PRIVATE.csv')
    assert audit._source_row.tolist() == list(range(2, 290))
    assert audit._raw_timestamp.iloc[144] != str(d._time.iloc[144])


def test_conflicting_times_without_gps_are_not_deduplicated(tmp_path):
    times = pack(tmp_path)
    def edit(d):
        d.loc[144:, 'timestamp_utc'] = (times[144:]-pd.Timedelta(hours=6)).strftime(TIME_FORMAT)
    change(tmp_path, 'WX9', edit)
    (tmp_path/'gps'/'WX9.nmea').unlink()
    result = analyze(tmp_path)
    assert len(result.frames['WX9']) == 288
    unresolved = issues(result, 'Unresolved backward sequence')
    assert len(unresolved) == 1
    assert unresolved.iloc[0].end_utc == result.end.strftime(TIME_FORMAT)
    assert issues(result, 'GPS-proven clock offset').empty


def test_flatline_and_spikes_are_separate(tmp_path):
    pack(tmp_path)
    def edit(d):
        d.loc[30:80, 'temp_c'] = 6.5
        d.loc[110, 'temp_c'] = -40
        d.loc[180, 'temp_c'] = 85
    change(tmp_path, 'WX9', edit)
    result = analyze(tmp_path)
    assert len(issues(result, 'Sensor flatline')) == 1
    assert len(issues(result, 'Isolated sensor spike')) == 2
    assert not result.flags[result.flags.channel.eq('pressure_hpa')].shape[0]


@pytest.mark.parametrize('channel,value', [('temp_c', 90), ('rh_pct', -2),
    ('pressure_hpa', 200), ('wind_kmh', -1), ('wind_dir_deg', 400),
    ('rain_mm', -1), ('ghi_wm2', 1700)])
def test_physical_bounds(tmp_path, channel, value):
    pack(tmp_path)
    change(tmp_path, 'WX9', lambda d: d.__setitem__(channel, value))
    result = analyze(tmp_path)
    assert not result.flags[(result.flags.channel == channel) & (result.flags.action == 'exclude')].empty


def test_persistent_humidity_fault_vs_small_overshoot(tmp_path):
    pack(tmp_path)
    def edit(d):
        d.loc[10, 'rh_pct'] = 101
        d.loc[50:150, 'rh_pct'] = np.tile([99, 104, 105], 34)[:101]
    change(tmp_path, 'WX9', edit)
    result = analyze(tmp_path)
    assert len(issues(result, 'Persistent humidity fault')) == 1
    assert len(issues(result, 'Minor humidity overshoot')) == 1
    assert issues(result, 'Outside screening bounds').empty


def test_true_saturation_and_calm_are_not_flatline_faults(tmp_path):
    pack(tmp_path)
    def edit(d):
        d['rh_pct'] = 100
        d['wind_kmh'] = 0
    change(tmp_path, 'WX9', edit)
    assert analyze(tmp_path).flags.empty


def test_gps_validation(tmp_path):
    time = pd.Timestamp('2031-01-02 03:00')
    path = tmp_path/'gps.nmea'
    good = rmc(time)
    invalid_checksum = good[:-2] + ('00' if good[-2:] != '00' else 'FF')
    invalid_date = good.replace('020131', '990131')
    body = invalid_date.split(',$', 1)[1].split('*')[0]
    invalid_date = f'{time:%Y-%m-%d %H:%M:%S},' + sentence(body)
    path.write_text('\n'.join([good, invalid_checksum, rmc(time, status='V'),
                             rmc(time, latitude='4060.0000'), invalid_date,
                             good.split('*')[0]])+'\n')
    fixes, _, rejected = parse_gps(path)
    assert len(fixes) == 1 and fixes.gps_utc.iloc[0] == time
    assert len(rejected) == 5
    assert {'bad checksum', 'void fix', 'coordinate out of range'}.issubset({r['reason'] for r in rejected})


@pytest.mark.parametrize('value,hemisphere,latitude', [('9000.1', 'N', True),
    ('18000.1', 'W', False), ('4000', 'Q', True), ('10500', 'N', False)])
def test_invalid_coordinates(value, hemisphere, latitude):
    with pytest.raises(ValueError):
        coordinate(value, hemisphere, latitude)


def test_gga_height_is_not_a_dated_clock_reference(tmp_path):
    path = tmp_path/'gps.nmea'
    body = 'GPGGA,030000.00,4000.0000,N,10500.0000,W,1,10,1.0,1500.0,M,-17.0,M,,'
    path.write_text('2031-01-02 03:00:00,'+sentence(body)+'\n')
    fixes, heights, rejected = parse_gps(path)
    assert fixes.empty and heights == [1500.] and not rejected


def test_location_conflict_does_not_change_metadata_or_weather(tmp_path):
    pack(tmp_path)
    meta = pd.read_csv(tmp_path/'stations.csv')
    meta.loc[0, 'lat'] = 41
    meta.to_csv(tmp_path/'stations.csv', index=False)
    result = analyze(tmp_path)
    f = issues(result, 'Location sources disagree').iloc[0]
    assert f.channel == 'metadata' and f.action == 'keep'
    assert result.stations.loc['WX9', 'lat'] == 41
    assert len(result.frames['WX9']) == 288


def test_pressure_step_is_supported_by_peers(tmp_path):
    pack(tmp_path, ids=('N1', 'N2', 'N3'), n=144*16)
    def edit(d):
        d.loc[144*8:, 'pressure_hpa'] += 7
    change(tmp_path, 'N1', edit)
    result = analyze(tmp_path)
    f = issues(result, 'Persistent pressure step')
    assert f.station_id.tolist() == ['N1']
    assert f.action.tolist() == ['exclude']


def test_shared_pressure_change_is_real_weather(tmp_path):
    pack(tmp_path, ids=('N1', 'N2', 'N3'), n=144*16)
    for station in ('N1', 'N2', 'N3'):
        def edit(d):
            d.loc[144*8:, 'pressure_hpa'] += 7
        change(tmp_path, station, edit)
    assert issues(analyze(tmp_path), 'Persistent pressure step').empty


def test_persistent_wind_scale_change(tmp_path):
    pack(tmp_path, ids=('N1', 'N2', 'N3'), n=144*28)
    def edit(d):
        d.loc[144*14:, 'wind_kmh'] *= .25
    change(tmp_path, 'N1', edit)
    result = analyze(tmp_path)
    f = issues(result, 'Persistent wind scale change')
    assert f.station_id.tolist() == ['N1'] and '0.25' in f.note.iloc[0]


def test_delayed_rain_release_needs_independent_evidence(tmp_path):
    pack(tmp_path, ids=('N1', 'N2', 'N3'), n=144*14)
    for station in ('N2', 'N3'):
        def edit(d):
            d.loc[144*5:144*5+59, 'rain_mm'] = .2
        change(tmp_path, station, edit)
    def release(d):
        d.loc[144*10:144*10+2, 'rain_mm'] = 8
    change(tmp_path, 'N1', release)
    result = analyze(tmp_path)
    assert issues(result, 'Blocked gauge / delayed release').station_id.tolist() == ['N1']


def test_coherent_weather_is_retained(tmp_path):
    ids = ('Q20', 'R30', 'T40')
    pack(tmp_path, ids=ids, n=144*10, start='2032-02-02')
    for station in ids:
        def edit(d):
            d.loc[144*8:144*8+23, 'temp_c'] += 10
            d.loc[144*8:144*8+23, 'rh_pct'] = 15
            d.loc[144*8:144*8+23, 'wind_kmh'] = 22
        change(tmp_path, station, edit)
    result = analyze(tmp_path)
    assert not issues(result, 'Coherent warm dry windy event').empty
    assert result.flags[result.flags.action.eq('exclude')].empty


def test_numeric_and_timestamp_errors(tmp_path):
    pack(tmp_path)
    def edit(d):
        d['rh_pct'] = d.rh_pct.astype(object)
        d.loc[5, 'rh_pct'] = 'broken'
        d.loc[7, 'timestamp_utc'] = 'not a date'
    change(tmp_path, 'WX9', edit)
    result = analyze(tmp_path)
    assert len(issues(result, 'Invalid numeric value')) == 1
    assert len(issues(result, 'Untimed source rows')) == 1
    assert len(issues(result, 'Missing observations')) == 1


def test_missing_one_station_file_is_flagged(tmp_path):
    pack(tmp_path, ids=('N1', 'N2'))
    (tmp_path/'data'/'N2.csv').unlink()
    result = analyze(tmp_path)
    assert issues(result, 'Unreadable weather file').station_id.tolist() == ['N2']


@pytest.mark.parametrize('problem', ['metadata', 'column', 'timestamps'])
def test_unusable_pack_errors_are_useful(tmp_path, problem):
    pack(tmp_path)
    if problem == 'metadata':
        (tmp_path/'stations.csv').unlink()
    elif problem == 'column':
        change(tmp_path, 'WX9', lambda d: d.drop(columns='temp_c'))
    else:
        change(tmp_path, 'WX9', lambda d: d.__setitem__('timestamp_utc', 'invalid'))
    with pytest.raises(ValueError, match='missing metadata|missing columns|no valid timestamps'):
        analyze(tmp_path)


def test_cli_contract_and_determinism(tmp_path):
    data = tmp_path/'pack'
    data.mkdir()
    pack(data, ids=('OTHER_ID',), start='2033-09-01')
    change(data, 'OTHER_ID', lambda d: d.__setitem__('wind_kmh', -3))
    script = Path(__file__).resolve().parents[1]/'checker.py'
    command = [sys.executable, str(script), str(data)]
    for _ in range(2):
        process = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
        assert process.returncode == 0, process.stderr
        content = (tmp_path/'flags.csv').read_bytes()
        if _ == 0:
            first = content
        else:
            assert content == first
    assert not (data/'flags.csv').exists()
    f = pd.read_csv(tmp_path/'flags.csv')
    assert list(f) == FIELDS and set(f.action) <= {'exclude', 'correct', 'keep'}
    for field in ['start_utc', 'end_utc']:
        assert f[field].str.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}').all()
    assert (f.start_utc <= f.end_utc).all()


def test_exposure_drift_only_withholds_bright_intervals(tmp_path):
    pack(tmp_path, ids=('N1', 'N2', 'N3'), n=144*35)
    def edit(d):
        drift = np.clip((np.arange(len(d))/144-10)/5, 0, 5)
        d['temp_c'] += drift*d.ghi_wm2/800
    change(tmp_path, 'N1', edit)
    result = analyze(tmp_path)
    f = issues(result, 'Possible sunlight heating bias')
    assert set(f.station_id) == {'N1'}
    d = result.frames['N1']
    for flag in f.itertuples():
        assert d.loc[d._time.between(flag.start_utc, flag.end_utc), 'ghi_wm2'].ge(500).all()


@pytest.mark.parametrize('channel', ['wind_kmh', 'ghi_wm2'])
def test_zero_sensor_needs_active_peers(tmp_path, channel):
    pack(tmp_path, ids=('N1', 'N2', 'N3'), n=144*3)
    change(tmp_path, 'N1', lambda d: d.__setitem__(channel, 0))
    assert issues(analyze(tmp_path), 'Unresponsive zero sensor').station_id.tolist() == ['N1']


@pytest.mark.parametrize('shift', [-60, 360])
def test_forward_and_initial_clock_offsets(tmp_path, shift):
    times = pack(tmp_path, reset=(0, shift))
    change(tmp_path, 'WX9', lambda d: d.__setitem__('timestamp_utc', (times-pd.Timedelta(minutes=shift)).strftime(TIME_FORMAT)))
    result = analyze(tmp_path)
    assert result.frames['WX9']._time.tolist() == times.tolist()
    assert len(issues(result, 'GPS-proven clock offset')) == 1


def test_report_matches_flags_and_coverage(tmp_path):
    from build_report import choose_visit, report_html
    pack(tmp_path, ids=('N1', 'N2', 'N3'), n=144*16)
    change(tmp_path, 'N1', lambda d: d.__setitem__('wind_kmh', -1))
    result = analyze(tmp_path)
    counts = coverage_summary(result)
    assert counts.loc['N1', 'wind_kmh'] == 0
    assert counts.loc['N1', 'temp_c'] == 144*16
    html = report_html(result)
    assert '<!doctype html>' in html and '0.0%' in html
    assert choose_visit(result)['station'] == 'N1'


def test_keep_flags_do_not_overlap_channel_exclusions(tmp_path):
    ids = ('N1', 'N2', 'N3')
    pack(tmp_path, ids=ids, n=144*10)
    for station in ids:
        def edit(d):
            d.loc[144*8:144*8+23, 'temp_c'] += 10
            d.loc[144*8:144*8+23, 'rh_pct'] = 15
            d.loc[144*8:144*8+23, 'wind_kmh'] = 22
        change(tmp_path, station, edit)
    change(tmp_path, 'N1', lambda d: d.__setitem__('pressure_hpa', 200))
    result = analyze(tmp_path)
    keep = result.flags[(result.flags.station_id == 'N1') & (result.flags.action == 'keep')]
    assert not keep.empty and set(keep.channel) == {'temp_c'}


def test_mountain_station_is_not_rejected_for_lower_pressure(tmp_path):
    pack(tmp_path, ids=('HIGH', 'LOW1', 'LOW2'), n=144*28)
    meta = pd.read_csv(tmp_path/'stations.csv')
    meta.loc[meta.station_id.eq('HIGH'), 'elevation_m'] = 3000
    meta.to_csv(tmp_path/'stations.csv', index=False)
    def edit(d):
        d['temp_c'] -= 15
        d['pressure_hpa'] -= 150
    change(tmp_path, 'HIGH', edit)
    assert analyze(tmp_path).flags.empty


def test_too_few_gps_fixes_cannot_prove_a_clock_correction(tmp_path):
    pack(tmp_path, reset=(0, 360))
    path = tmp_path/'gps'/'WX9.nmea'
    path.write_text('\n'.join(path.read_text().splitlines()[:2])+'\n')
    result = analyze(tmp_path)
    assert issues(result, 'GPS-proven clock offset').empty
    assert len(issues(result, 'Unresolved clock evidence')) == 1


def test_report_cli_accepts_empty_flags(tmp_path, monkeypatch):
    from build_report import main
    data = tmp_path/'pack'
    data.mkdir()
    pack(data)
    analyze(data).flags.to_csv(tmp_path/'flags.csv', index=False)
    monkeypatch.chdir(tmp_path)
    main([str(data)])
    assert (tmp_path/'report.html').exists()
    assert (tmp_path/'coverage.csv').exists()


def test_report_cli_refuses_stale_flags(tmp_path, monkeypatch):
    from build_report import main
    data = tmp_path/'pack'
    data.mkdir()
    pack(data)
    analyze(data).flags.to_csv(tmp_path/'flags.csv', index=False)
    change(data, 'WX9', lambda d: d.__setitem__('wind_kmh', -1))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as error:
        main([str(data)])
    assert error.value.code == 2
    assert not (tmp_path/'report.html').exists()
