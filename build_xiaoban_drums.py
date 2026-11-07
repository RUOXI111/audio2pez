"""Experimental percussion-led chart; no grid fills, no forced BPM snapping."""
import copy, csv, json, math, zipfile
from pathlib import Path
from fractions import Fraction
import numpy as np
import librosa
import soundfile as sf
from scipy.ndimage import median_filter, gaussian_filter1d
from scipy.signal import find_peaks

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'songs' / '小半.ogg'
OLD = ROOT / 'output' / '小半_副歌修订_v2' / 'song_c784062b_hard_chorus_v2.pez'
OUT = ROOT / 'output' / '小半_鼓点对照_v3'
OUT.mkdir(parents=True, exist_ok=True)
SR, HOP, FFT = 22050, 128, 1024
y, sr = librosa.load(str(SRC), sr=SR)
candidates = []
# Chunked HPSS avoids large whole-track median-filter allocations.
for start in np.arange(0, len(y)/SR, 30.0):
    lo, hi = max(0., start-1.5), min(len(y)/SR, start+31.5)
    segment = y[int(lo*SR):int(hi*SR)]
    spec = librosa.stft(segment, n_fft=FFT, hop_length=HOP)
    _, perc = librosa.decompose.hpss(spec, kernel_size=31, margin=(2., 4.))
    mag = np.abs(perc)
    freqs = librosa.fft_frequencies(sr=SR, n_fft=FFT)
    times = librosa.frames_to_time(np.arange(mag.shape[1]), sr=SR, hop_length=HOP)+lo
    for label, low, high in [('low',40,200), ('body',200,4500)]:
        band = mag[(freqs>=low)&(freqs<high)]
        energy = np.sqrt(np.mean(band*band, axis=0))
        flux = np.mean(np.maximum(np.diff(np.log1p(10*band),axis=1,prepend=np.log1p(10*band[:,:1])),0),axis=0)
        flux = gaussian_filter1d(flux, .6)
        baseline = median_filter(flux, size=173, mode='nearest')
        residual = np.maximum(flux-baseline, 0)
        scale = max(float(np.percentile(residual,95)),1e-6)
        peaks, props = find_peaks(residual, distance=int(.12*SR/HOP), prominence=.20*scale, height=.30*scale)
        floor = max(float(np.percentile(energy,65))*.35,1e-4)
        for idx in peaks:
            if energy[idx] < floor:
                continue
            # Onset rise, not spectral-flux maximum; limit backtrack to ~35 ms.
            onset = int(idx)
            stop = max(0, idx-6)
            while onset>stop and flux[onset-1]>.20*flux[idx] and flux[onset-1]<=flux[onset]:
                onset-=1
            t = float(times[onset])
            if not start <= t < min(start+30,len(y)/SR) or t < .8:
                continue
            candidates.append({'time':t,'band':label,'strength':float(residual[idx]/scale),'energy':float(energy[idx])})
    print('Analyzed percussion',round(start),flush=True)
# Strongest measured hit wins within 200 ms. Never add a note without a detected transient.
selected=[]
for p in sorted(candidates,key=lambda p:p['strength'],reverse=True):
    if all(abs(p['time']-q['time'])>=.20 for q in selected):
        selected.append(p)
selected.sort(key=lambda p:p['time'])
assert selected
with zipfile.ZipFile(OLD) as z:
    assets={n:z.read(n) for n in z.namelist()}
chartname=next(n for n in assets if n.endswith('.json'))
old=json.loads(assets[chartname])
chart=copy.deepcopy(old)
proto=copy.deepcopy(next(n for line in chart['judgeLineList'] for n in line.get('notes',[]) if not n.get('isFake')))
def beat(t):
    f=Fraction(round(t*165/60*4800),4800)
    return [f.numerator//f.denominator,f.numerator%f.denominator,f.denominator]
notes=[]
for i,p in enumerate(selected):
    n=copy.deepcopy(proto)
    n.update(type=1,startTime=beat(p['time']),endTime=beat(p['time']),positionX=(-150 if i%2==0 else 150),isFake=0,above=1,alpha=255,speed=1.,yOffset=0.,visibleTime=999999.)
    notes.append(n)
for line in chart['judgeLineList']:
    line['notes']=[]
    line['numOfNotes']=0
chart['judgeLineList'][0]['notes']=notes
chart['judgeLineList'][0]['numOfNotes']=len(notes)
chart['META'].update(name='小半 [鼓点对照 v3]',id='xiaoban_drums_v3',level='DRUM TEST',offset=0,charter='audio2pez percussion experiment')
chart['BPMList']=[{'startTime':[0,0,1],'bpm':165.}]
# Retain original audio and image byte-for-byte.
assets[chartname]=json.dumps(chart,ensure_ascii=False,indent=2).encode('utf-8')
meta=chart['META']
assets['info.txt']=('\n'.join(['#','Name: '+meta['name'],'Path: '+meta['id'],'Song: '+meta['song'],'Picture: '+meta['background'],'Chart: '+chartname,'Level: '+meta['level'],'Composer: '+meta['composer'],'Charter: '+meta['charter']])+ '\n').encode('utf-8')
package=OUT/'xiaoban_drums_v3.pez'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
    for name,raw in assets.items():z.writestr(name,raw)
with zipfile.ZipFile(package) as z:
    assert z.testzip() is None
    check=json.loads(z.read(chartname))
    assert check['META']['song'] in z.namelist() and check['META']['background'] in z.namelist()
    restored=[(n['startTime'][0]+n['startTime'][1]/n['startTime'][2])*60/165 for n in check['judgeLineList'][0]['notes']]
    error=max(abs(a-p['time']) for a,p in zip(restored,selected))
    assert error<.0001
with (OUT/'detected_hits.csv').open('w',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=['time','band','strength','energy']);writer.writeheader();writer.writerows(selected)
# Identical music segment and click level for both comparisons.
a,b=50.,86.
clip=y[int(a*SR):int(b*SR)]
click_t=np.arange(int(.027*SR))/SR
click=(np.sin(2*np.pi*1800*click_t)*np.exp(-click_t*150)).astype(np.float32)*.24
def preview(ts,name):
    out=clip.copy()*.65
    for t in ts:
        if a<=t<b:
            idx=int((t-a)*SR);length=min(len(click),len(out)-idx)
            out[idx:idx+length]+=click[:length]
    with sf.SoundFile(str(OUT/name), 'w', samplerate=SR, channels=1, format='OGG', subtype='VORBIS') as f:
        for start in range(0,len(out),4096):
            f.write(np.clip(out[start:start+4096],-.99,.99))
oldtimes=[(n['startTime'][0]+n['startTime'][1]/n['startTime'][2])*60/165+old['META']['offset']/1000 for l in old['judgeLineList'] for n in l.get('notes',[]) if not n.get('isFake')]
preview(oldtimes,'compare_v2_50-86s.ogg')
preview(restored,'compare_v3_50-86s.ogg')
summary={'notes':len(notes),'candidate_count':len(candidates),'offset_ms':0,'time_roundtrip_max_ms':error*1000,'minimum_gap_ms':min(np.diff(restored))*1000,'chorus_notes':[sum(a<=t<b for t in restored) for a,b in [(51.3,85.5),(142.6,177.5),(229.9,264.6)]],'method':'HPSS percussive spectral transients in low and body bands; 200ms nonmaximum suppression; onset-rise backtracking; no grid fill; all taps','limitations':'Percussive separation is approximate and can include piano/guitar/vocal attacks; not manually auditioned; no guarantee of true drum matching.'}
(OUT/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
print(package)
