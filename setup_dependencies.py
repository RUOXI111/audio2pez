"""One-click setup helper: pinned wheels, SHA256 validation, no pip resolver."""
import argparse,hashlib,importlib.metadata,json,os,subprocess,sys,time,urllib.request
from pathlib import Path

def say(text):print(text,flush=True)
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def check_versions(lock):
    missing=[]
    for p in lock['packages']:
        try:version=importlib.metadata.version(p['name'])
        except importlib.metadata.PackageNotFoundError:version=None
        if version!=p['version']:missing.append((p,version))
    return missing
def fetch(package,cache,offline):
    target=cache/package['filename']
    if target.is_file() and target.stat().st_size==package['size'] and digest(target)==package['sha256']:
        say('CACHE '+package['filename']);return target
    if offline:raise RuntimeError('Offline wheel missing or hash mismatch: '+package['filename'])
    if not package['url'].startswith('https://files.pythonhosted.org/'):
        raise RuntimeError('Rejected non-PyPI wheel URL')
    cache.mkdir(parents=True,exist_ok=True)
    for attempt in range(3):
        temporary=cache/(package['filename']+'.download')
        try:
            say('DOWNLOAD '+package['filename'])
            req=urllib.request.Request(package['url'],headers={'User-Agent':'Audio2Phira-Setup/1.0'})
            with urllib.request.urlopen(req,timeout=45) as response,temporary.open('wb') as out:
                while True:
                    block=response.read(1024*1024)
                    if not block:break
                    out.write(block)
            if temporary.stat().st_size!=package['size'] or digest(temporary)!=package['sha256']:
                raise RuntimeError('SHA256 mismatch: '+package['filename'])
            os.replace(temporary,target);return target
        except Exception:
            if attempt==2:raise
            time.sleep(attempt+1)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--offline',action='store_true');parser.add_argument('--check',action='store_true');parser.add_argument('--cache-only',action='store_true')
    args=parser.parse_args();root=Path(args.root).resolve()
    if sys.version_info[:2]!=(3,12) or sys.maxsize<=2**32:raise RuntimeError('CPython 3.12 x64 required')
    lock=json.loads((root/'installer_wheels.lock.json').read_text(encoding='utf-8'))
    missing=check_versions(lock)
    if args.check:
        for p,current in missing:say(f'MISMATCH {p["name"]}: {current} -> {p["version"]}')
        if missing:return 2
        say('Pinned package versions OK');return 0
    targets=lock['packages'] if args.cache_only else [p for p,_ in missing]
    cache=root/'wheels'
    wheels=[fetch(p,cache,args.offline) for p in targets]
    if args.cache_only:
        say('Complete verified offline wheel cache ready');return 0
    if wheels:
        # All dependencies are explicit; no index lookups and no resolver backtracking.
        cmd=[sys.executable,'-m','pip','install','--no-index','--no-deps','--disable-pip-version-check',*[str(p) for p in wheels]]
        subprocess.run(cmd,check=True,timeout=600)
    if check_versions(lock):raise RuntimeError('Installed versions still mismatch')
    subprocess.run([sys.executable,'-m','pip','check'],check=True,timeout=60)
    say('Dependency installation verified');return 0
if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    try:sys.exit(main())
    except Exception as exc:say('SETUP ERROR: '+str(exc));sys.exit(1)
