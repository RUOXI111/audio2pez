"""Local desktop integration checks; keeps test artifacts in a dedicated folder."""
import copy,json,math,sys,zipfile
from pathlib import Path
import numpy as np
import soundfile as sf
from desktop_worker import run,validate
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'/'_desktop_tests'
OUT.mkdir(parents=True,exist_ok=True)
base={'audio':str(ROOT/'test_song.wav'),'title':'桌面测试','artist':'Test','mode':'standard','difficulty':'hard','all_tiers':False,'key_mode':'4k','density':1.,'bpm':128,'chorus':'10-20,25-35','line_fx':'none','preview_start':10,'preview_duration':10,'output_dir':str(OUT),'seed':42}
checks=[]
def check(job):
    result=run(job)
    y,sr=sf.read(result['preview']);assert len(y)>0 and np.isfinite(y).all()
    assert abs(len(y)/sr-result['preview_duration'])<1e-4
    for item in result['charts']:
        with zipfile.ZipFile(item['path']) as z:
            assert z.testzip() is None
            d=json.loads(z.read(next(n for n in z.namelist() if n.endswith('.json'))))
            assert d['META']['song'] in z.namelist() and d['META']['background'] in z.namelist()
            if job['mode']=='drums':
                assert all(n['type']==1 for l in d['judgeLineList'] for n in l.get('notes',[]))
    print('PASS',job['mode'],len(result['charts']),'charts')
    checks.append(result)
    return result
a=check(base)
b=check(dict(base,all_tiers=True,line_fx='mix'))
c=check(dict(base,mode='drums',chorus='',all_tiers=True))
# Decode a real AAC/M4A fixture using PyAV.
import av
m4a=OUT/'fixture.m4a'
y,sr=sf.read(ROOT/'test_song.wav',dtype='float32',always_2d=True,frames=44100*12)
if y.shape[1]==1:y=np.repeat(y,2,axis=1)
with av.open(str(m4a),'w') as container:
    stream=container.add_stream('aac',rate=sr);stream.layout='stereo'
    for start in range(0,len(y),1024):
        frame=av.AudioFrame.from_ndarray(np.ascontiguousarray(y[start:start+1024].T),format='fltp',layout='stereo');frame.sample_rate=sr
        for pkt in stream.encode(frame):container.mux(pkt)
    for pkt in stream.encode(None):container.mux(pkt)
d=check(dict(base,audio=str(m4a),chorus='',preview_start=1,preview_duration=5))
# External absolute-time points and invalid request checks.
points=OUT/'points.json'
points.write_text(json.dumps({'bpm':128,'points':[{'time_sec':float(t)} for t in np.arange(1,40,.5)]}),encoding='utf-8')
e=check(dict(base,points=str(points)))
for field,value in [('audio','no_such_song.wav'),('bpm',float('nan')),('density',0),('offset_ms',9999)]:
    try:validate(dict(base,**{field:value}))
    except ValueError:print('PASS rejected',field)
    else:raise AssertionError('Accepted invalid '+field)
try:run(dict(base,preview_start=999))
except ValueError:print('PASS rejected preview beyond song')
else:raise AssertionError('Accepted bad preview')
print('DESKTOP TESTS PASSED:',len(checks),'successful generation jobs')
