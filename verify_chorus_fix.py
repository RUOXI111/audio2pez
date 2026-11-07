"""Regression checks for timing, section coverage and the main CLI paths."""
import json
import math
from pathlib import Path
import subprocess
import sys
import zipfile

import numpy as np
from audio_analyze import _detect_sections, parse_time_ranges
from detector import detect_result
from generate import _chart_offset_ms

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output' / '_chorus_verification'

def check_package(path):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        names = z.namelist()
        chart = json.loads(z.read(next(n for n in names if n.endswith('.json'))))
        assert chart['META']['song'] in names
        assert chart['META']['background'] in names
        notes = [n for line in chart['judgeLineList'] for n in line.get('notes', [])]
        assert notes
        for n in notes:
            a, b = n['startTime'], n['endTime']
            assert all(math.isfinite(float(v)) for v in a + b)
            assert a[2] > 0 and b[2] > 0
            assert a[0] + a[1]/a[2] <= b[0] + b[1]/b[2]
    return chart

assert parse_time_ranges('0:51.3-1:25.5,2:22.6-2:57.5') == [(51.3,85.5),(142.6,177.5)]
t = np.arange(0, 10.1, .1)
sections = _detect_sections(np.ones(len(t)), t, 10.1, 165)
assert sections[0]['start_time'] == 0 and sections[-1]['end_time'] == 10.1
sections = _detect_sections(np.ones(len(t)), t, 10.1, 165, '2-5')
assert all((s['label'] == 'chorus') == (2 <= (s['start_time']+s['end_time'])/2 < 5) for s in sections)

r = detect_result(str(ROOT/'test_song.wav'), bpm=128)
offset = _chart_offset_ms(r)/1000
error = max(abs(p['beat_tick']/480*60/128 + offset - p['time_sec']) for p in r['points'])
assert error < .002, error
assert _chart_offset_ms({'bpm':120,'points':[{'time_sec':1,'beat_tick':960}]}) == 0
assert _chart_offset_ms({'bpm':120,'points':[{'time_sec':1.25,'beat_tick':960}]}) == 250

OUT.mkdir(parents=True, exist_ok=True)
points = OUT/'points.json'
points.write_text(json.dumps(r), encoding='utf-8')
cases = [
    ['test_song.wav','--bpm','128'],
    ['test_song.wav','--bpm','128','--all-tiers','--key','4k','--line-fx','mix','--chorus','10-20,25-35'],
    ['test_song.wav','--from-points',str(points),'--chorus','10-20'],
]
for i, args in enumerate(cases):
    dest = OUT/str(i)
    subprocess.run([sys.executable, 'main.py', *args, '--outdir', str(dest)], cwd=ROOT, check=True)
    packages = list(dest.glob('*.pez'))
    assert len(packages) == (5 if i == 1 else 1)
    for p in packages:
        check_package(p)
    print(f'PASS CLI case {i}: {len(packages)} package(s)')
for p in (ROOT/'output'/'小半').glob('*.pez'):
    check_package(p)
print(f'PASS timing round-trip: max error {error*1000:.3f} ms')
print('PASS section boundaries and 小半 packages')
