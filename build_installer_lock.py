"""Developer helper: freeze verified Windows CPython 3.12 package wheels."""
import concurrent.futures,importlib.metadata as metadata,json,time,urllib.request
from pathlib import Path
from pip._vendor.packaging.tags import sys_tags
from pip._vendor.packaging.utils import parse_wheel_filename
ROOT=Path(__file__).resolve().parent
tags={t:i for i,t in enumerate(sys_tags())}
def resolve(item):
    name,version=item
    url=f'https://pypi.org/pypi/{name}/{version}/json'
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Audio2Phira-Setup/1.0'})
            with urllib.request.urlopen(req,timeout=45) as response:data=json.load(response)
            break
        except Exception:
            if attempt==2:raise
            time.sleep(attempt+1)
    choices=[]
    for f in data['urls']:
        if f['packagetype']!='bdist_wheel' or f.get('yanked'):continue
        _,_,_,wheel_tags=parse_wheel_filename(f['filename'])
        ranks=[tags[t] for t in wheel_tags if t in tags]
        if ranks:choices.append((min(ranks),f))
    if not choices:raise RuntimeError(f'No compatible wheel: {name}=={version}')
    f=min(choices,key=lambda x:x[0])[1]
    print(name,version,f['filename'],flush=True)
    return {'name':name,'version':version,'filename':f['filename'],'url':f['url'],'sha256':f['digests']['sha256'],'size':f['size']}
if __name__=='__main__':
    installed=sorted((d.metadata['Name'],d.version) for d in metadata.distributions() if d.metadata['Name'].lower()!='pip')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:packages=list(pool.map(resolve,installed))
    dest=ROOT/'installer_wheels.lock.json'
    if dest.exists():raise RuntimeError('Refusing to overwrite existing lock; review it first')
    dest.write_text(json.dumps({'schema':1,'python':'3.12','platform':'win_amd64','packages':packages},indent=2),encoding='utf-8')
    print('LOCK_READY',len(packages),sum(p['size'] for p in packages))
