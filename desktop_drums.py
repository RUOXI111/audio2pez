"""Local percussion-led chart mode. Experimental HPSS, not isolated drum stems."""
import csv
from fractions import Fraction
from pathlib import Path
import numpy as np
import librosa
from scipy.ndimage import median_filter, gaussian_filter1d
from scipy.signal import find_peaks
from config import DIFFICULTY_PRESETS
from detector import detect_bpm
from packager import build_chart_json, pack_pez


def detect_hits(audio, log=print):
    sr, hop, fft = 22050, 128, 1024
    y, _ = librosa.load(str(audio), sr=sr, mono=True)
    if not len(y) or np.max(np.abs(y)) < 1e-5:
        raise ValueError('音频为空或接近静音，无法检测鼓点。')
    duration = len(y)/sr
    candidates=[]
    for start in np.arange(0, duration, 30.):
        lo,hi=max(0.,start-1.5),min(duration,start+31.5)
        spec=librosa.stft(y[int(lo*sr):int(hi*sr)],n_fft=fft,hop_length=hop)
        _,perc=librosa.decompose.hpss(spec,kernel_size=31,margin=(2.,4.))
        mag=np.abs(perc)
        freqs=librosa.fft_frequencies(sr=sr,n_fft=fft)
        times=librosa.frames_to_time(np.arange(mag.shape[1]),sr=sr,hop_length=hop)+lo
        for label,low,high in [('low',40,200),('body',200,4500)]:
            band=mag[(freqs>=low)&(freqs<high)]
            energy=np.sqrt(np.mean(band*band,axis=0))
            logged=np.log1p(10*band)
            flux=np.mean(np.maximum(np.diff(logged,axis=1,prepend=logged[:,:1]),0),axis=0)
            flux=gaussian_filter1d(flux,.6)
            residual=np.maximum(flux-median_filter(flux,size=173,mode='nearest'),0)
            scale=max(float(np.percentile(residual,95)),1e-6)
            peaks,_=find_peaks(residual,distance=int(.12*sr/hop),prominence=.20*scale,height=.30*scale)
            floor=max(float(np.percentile(energy,65))*.35,1e-4)
            for idx in peaks:
                if energy[idx]<floor:continue
                onset=int(idx)
                while onset>max(0,idx-6) and flux[onset-1]>.20*flux[idx] and flux[onset-1]<=flux[onset]:
                    onset-=1
                t=float(times[onset])
                if start<=t<min(start+30,duration) and t>=.8:
                    candidates.append({'time':t,'band':label,'strength':float(residual[idx]/scale),'energy':float(energy[idx])})
        log(f'鼓点分析 {min(start+30,duration):.0f}/{duration:.0f} 秒')
    return y,sr,candidates


def select_hits(candidates, gap):
    # Bin-based suppression makes long-song selection linear-ish rather than quadratic.
    bins={}
    for hit in sorted(candidates,key=lambda x:x['strength'],reverse=True):
        k=int(hit['time']/gap)
        neighbors=[p for i in (k-1,k,k+1) for p in bins.get(i,[])]
        if all(abs(hit['time']-p['time'])>=gap for p in neighbors):
            bins.setdefault(k,[]).append(hit)
    return sorted((p for values in bins.values() for p in values),key=lambda x:x['time'])


def generate_drums(job,audio,outdir,log=print):
    y,sr,candidates=detect_hits(audio,log)
    if not candidates:raise ValueError('没有检测到可用的打击乐瞬态，请尝试常规模式。')
    bpm=float(job.get('bpm') or detect_bpm(y,sr))
    tiers=list(DIFFICULTY_PRESETS) if job.get('all_tiers') else [job['difficulty']]
    gaps={'easy':.40,'normal':.28,'hard':.20,'expert':.16,'master':.12}
    count={'auto':4,'2k':2,'4k':4,'6k':6}[job['key_mode']]
    lanes=np.linspace(-225,225,count).tolist()
    left,right=lanes[:count//2],lanes[count//2:]
    results={}
    for tier in tiers:
        hits=select_hits(candidates,max(.09,gaps[tier]/job['density']))
        notes=[]
        def beat(t):
            f=Fraction(round(t*bpm/60*4800),4800)
            return [f.numerator//f.denominator,f.numerator%f.denominator,f.denominator]
        for i,hit in enumerate(hits):
            hand=left if i%2==0 else right
            pos=hand[(i//2)%len(hand)]
            when=beat(hit['time'])
            notes.append({'above':1,'alpha':255,'endTime':when,'isFake':0,'positionX':pos,'size':1.,'speed':1.,'startTime':when,'type':1,'visibleTime':999999.,'yOffset':0.})
        chart_id='drums_'+tier
        meta={'id':chart_id,'name':job['title'],'level':tier.upper()+' / DRUM','composer':job['artist'],'charter':job['charter'],'song':chart_id+Path(audio).suffix,'background':chart_id+'.png','offset':0,'duration':len(y)/sr}
        chart=build_chart_json(notes,bpm,meta)
        path=pack_pez(str(audio),str(outdir),chart,image_path=job.get('cover') or None)
        results[tier]=str(path)
        with (Path(outdir)/(tier+'_hits.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['time','band','strength','energy']);w.writeheader();w.writerows(hits)
        log(f'{tier}: {len(notes)} 个实际检测瞬态，最小间距 {max(.09,gaps[tier]/job["density"]):.3f}s')
    return {'results':results,'log':'鼓点模式：仅 Tap，不按 BPM 网格补点；分离可能混入其他乐器。'},bpm
