"""Isolated desktop worker. Usage: python -u desktop_worker.py job.json"""
import json, math, os, random, re, sys, traceback, uuid, zipfile
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def log(message):print(message,flush=True)

def number(value,name,minimum,maximum):
    try: n=float(value)
    except (TypeError,ValueError):raise ValueError(name+' 必须是数字')
    if not math.isfinite(n) or not minimum<=n<=maximum:raise ValueError(f'{name} 必须在 {minimum}–{maximum} 之间')
    return n

def validate(raw):
    j=dict(raw)
    p=Path(j.get('audio') or '')
    if not p.is_file():raise ValueError('请选择存在的音频文件。')
    if p.suffix.lower() not in ('.mp3','.wav','.ogg','.flac','.m4a','.aac'):
        raise ValueError('支持 MP3 / WAV / OGG / FLAC / M4A / AAC，不支持加密缓存文件。')
    j['audio']=str(p.resolve())
    for field in ('cover','points'):
        v=j.get(field)
        if v and not Path(v).is_file():raise ValueError(field+' 文件不存在。')
        j[field]=str(Path(v).resolve()) if v else None
    j['title']=str(j.get('title') or p.stem).strip() or p.stem
    j['artist']=str(j.get('artist') or 'Unknown')
    j['charter']=str(j.get('charter') or 'audio2pez Desktop')
    for key,default,allowed in [('mode','standard',('standard','drums')),('difficulty','hard',('easy','normal','hard','expert','master')),('key_mode','auto',('auto','2k','4k','6k')),('line_fx','none',('none','mix','breathe','alpha_pulse'))]:
        j[key]=j.get(key,default)
        if j[key] not in allowed:raise ValueError('不支持的选项: '+key)
    j['density']=number(j.get('density',1),'密度',.7,1.6)
    j['bpm']=number(j['bpm'],'BPM',30,300) if j.get('bpm') not in (None,'') else None
    j['offset_ms']=number(j.get('offset_ms',0),'时间微调',-500,500)
    j['preview_start']=number(j.get('preview_start',0),'试听开始秒数',0,86400)
    j['preview_duration']=number(j.get('preview_duration',30),'试听长度',5,60)
    j['chorus']=str(j.get('chorus') or '').strip()
    j['all_tiers']=bool(j.get('all_tiers',False))
    j['seed']=int(j.get('seed',42))
    j['output_dir']=str(Path(j.get('output_dir') or ROOT/'output'/'Desktop').resolve())
    if j['mode']=='drums' and (j['points'] or j['chorus'] or j['line_fx']!='none'):
        raise ValueError('鼓点模式不使用 points、副歌覆盖或判定线特效，请清空这些选项。')
    return j

def prepare_audio(job,work):
    import soundfile as sf
    src=Path(job['audio'])
    # Preserve normal supported inputs. M4A/AAC decode to lossless PCM WAV via bundled PyAV.
    if src.suffix.lower() in ('.m4a','.aac'):
        import av
        target=work/'decoded_audio.wav'
        frames=0
        with av.open(str(src)) as container, sf.SoundFile(str(target),'w',samplerate=44100,channels=2,format='WAV',subtype='PCM_16') as out:
            if not container.streams.audio:raise ValueError('文件没有音频流。')
            resampler=av.AudioResampler(format='s16',layout='stereo',rate=44100)
            for frame in container.decode(container.streams.audio[0]):
                for converted in resampler.resample(frame):
                    data=converted.to_ndarray().reshape(-1,2)
                    out.write(data);frames+=len(data)
            for converted in resampler.resample(None):
                data=converted.to_ndarray().reshape(-1,2);out.write(data);frames+=len(data)
        if not frames:raise ValueError('音频解码后为空。')
        src=target
    info=sf.info(str(src))
    if info.duration<=1:raise ValueError('音频太短，请选择超过 1 秒的歌曲。')
    if info.duration>1800:raise ValueError('桌面版单曲上限为 30 分钟，请先截取片段。')
    if job['preview_start']>=info.duration:raise ValueError('试听开始时间超过歌曲长度。')
    if job.get('cover'):
        from PIL import Image
        with Image.open(job['cover']) as im:im.verify()
    return str(src),info.duration

def verify_points(path,bpm,duration):
    import numpy as np
    from generate import coerce_points_dict
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(data,(dict,list)):raise ValueError('points 必须是 JSON 对象或数组。')
    if isinstance(data,dict) and data.get('bpm_changes'):
        raise ValueError('桌面版暂不支持变速 points，请使用恒定 BPM 数据。')
    result=coerce_points_dict(data,bpm)
    if not 30<=result['bpm']<=300 or result['ticks_per_beat']<=0:raise ValueError('points BPM 或 ticks_per_beat 无效。')
    tempos=result['tempo_events']
    if any(abs(float(e.get('bpm',result['bpm']))-result['bpm'])>1e-6 for e in tempos):
        raise ValueError('桌面版暂不支持变速 points。')
    if not result['points']:raise ValueError('points 内没有音符时间点。')
    diffs=[]
    for p in result['points']:
        t=p['time_sec'];tick=p['beat_tick']
        if not math.isfinite(t) or not 0<=t<=duration or tick<0:raise ValueError('points 存在无效或超出音频范围的时间。')
        diffs.append(t-tick/result['ticks_per_beat']*60/result['bpm'])
    if np.max(np.abs(np.array(diffs)-np.median(diffs)))>.03:
        raise ValueError('points 的 tick 与音频秒数不符合恒定 BPM，无法可靠对齐。')
    result['duration_sec']=duration
    return result

def adjust_and_check(path,offset_ms):
    p=Path(path)
    with zipfile.ZipFile(p) as z:
        if z.testzip() is not None:raise ValueError('谱包 CRC 检查失败')
        content={n:z.read(n) for n in z.namelist()}
    name=next(n for n in content if n.endswith('.json'))
    d=json.loads(content[name]);d['META']['offset']+=int(round(offset_ms))
    if len(d['BPMList'])!=1:raise ValueError('桌面版预听暂只支持恒定 BPM 谱面。')
    bpm=d['BPMList'][0]['bpm'];off=d['META']['offset']/1000
    times=[];notes=[]
    for line in d['judgeLineList']:
        for n in line.get('notes',[]):
            for field in ('startTime','endTime'):
                if n[field][2]<=0:raise ValueError('音符分母无效')
            s=n['startTime'][0]+n['startTime'][1]/n['startTime'][2]
            e=n['endTime'][0]+n['endTime'][1]/n['endTime'][2]
            if not math.isfinite(s+e) or s<0 or e<s:raise ValueError('音符时序无效')
            if not n.get('isFake'):times.append(s*60/bpm+off);notes.append(n)
    if not notes:raise ValueError('生成谱面为空，请更换模式或输入。')
    for field in ('song','background'):
        if d['META'][field] not in content:raise ValueError('谱包缺少资源: '+field)
    content[name]=json.dumps(d,ensure_ascii=False,indent=2).encode('utf-8')
    tmp=p.with_suffix('.pez.tmp')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for key,value in content.items():z.writestr(key,value)
    os.replace(tmp,p)
    p.with_suffix('.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'path':str(p),'notes':len(notes),'level':d['META']['level']},times,bpm

def make_preview(audio,times,start,length,target):
    import librosa,numpy as np,soundfile as sf
    y,sr=librosa.load(audio,sr=22050,mono=True,offset=start,duration=length)
    if not len(y):raise ValueError('试听片段为空')
    out=y*.65
    t=np.arange(int(sr*.027))/sr
    click=(.24*np.sin(2*np.pi*1800*t)*np.exp(-150*t)).astype(np.float32)
    # Chords produce one audible click at their shared timestamp.
    for seconds in sorted(set(round(v,5) for v in times)):
        index=int(round((seconds-start)*sr))
        if 0<=index<len(out):
            n=min(len(click),len(out)-index);out[index:index+n]+=click[:n]
    with sf.SoundFile(str(target),'w',samplerate=sr,channels=1,format='WAV',subtype='PCM_16') as f:
        for i in range(0,len(out),4096):f.write(np.clip(out[i:i+4096],-.99,.99))
    return len(out)/sr

def run(raw):
    job=validate(raw)
    from audio_analyze import parse_time_ranges
    ranges=parse_time_ranges(job['chorus'])
    if any(not math.isfinite(a+b) or a<0 or b<=a for a,b in ranges):raise ValueError('副歌区间无效')
    slug=re.sub(r'[<>:"/\\|?*]','_',job['title']).strip(' .')[:50] or 'song'
    out=Path(job['output_dir'])/(slug+'_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    out.mkdir(parents=True)
    try:
        (out/'settings.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
        log('检查音频和设置…')
        audio,duration=prepare_audio(job,out)
        if any(b>duration for a,b in ranges):raise ValueError('副歌区间超过歌曲长度。')
        import numpy as np
        random.seed(job['seed']);np.random.seed(job['seed']%(2**32))
        if job['mode']=='drums':
            from desktop_drums import generate_drums
            result,_=generate_drums(job,audio,out,log)
        else:
            from generate import generate,arrange
            common=dict(difficulty=job['difficulty'],all_tiers=job['all_tiers'],image_path=job['cover'],title=job['title'],artist=job['artist'],charter_name=job['charter'],outdir=str(out),density_mult=job['density'],line_fx=job['line_fx'],key_mode=job['key_mode'],chorus=job['chorus'])
            log('分析音频并排谱，请稍候…')
            if job['points']:
                data=verify_points(job['points'],job['bpm'],duration)
                result=arrange(data,audio_path=audio,**common)
            else:result=generate(audio_path=audio,bpm=job['bpm'],**common)
        log(result['log'])
        charts=[];time_by_tier={}
        for tier,path in result['results'].items():
            item,times,bpm=adjust_and_check(path,job['offset_ms']);item['tier']=tier
            charts.append(item);time_by_tier[tier]=times
        preview_tier=job['difficulty'] if job['difficulty'] in time_by_tier else next(iter(time_by_tier))
        preview=out/'preview.wav'
        log('生成音乐＋判定提示音试听…')
        preview_length=make_preview(audio,time_by_tier[preview_tier],job['preview_start'],job['preview_duration'],preview)
        report=out/'report.json'
        payload={'output_dir':str(out),'charts':charts,'preview':str(preview),'preview_tier':preview_tier,'preview_duration':preview_length,'report':str(report),'bpm':bpm,'duration':duration,'warning':'自动谱需要人工试听和试玩；鼓点分离可能混入其他乐器。'}
        report.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
        log('完成：谱包资源校验通过。')
        return payload
    except BaseException:
        (out/'error.log').write_text(traceback.format_exc(),encoding='utf-8')
        raise

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    if hasattr(sys.stderr,'reconfigure'):sys.stderr.reconfigure(encoding='utf-8',errors='replace')
    try:
        request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
        payload=run(request)
        print('RESULT_JSON:'+json.dumps(payload,ensure_ascii=False),flush=True)
    except Exception as exc:
        traceback.print_exc();log('生成失败：'+str(exc));sys.exit(1)
