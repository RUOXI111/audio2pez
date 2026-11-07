import json,sys,struct
from pathlib import Path
try:
    import tkinter,venv,ensurepip
    ok=sys.version_info[:2]==(3,12) and struct.calcsize('P')==8
    result={'ok':ok,'version':sys.version.split()[0],'base':str(Path(sys.base_prefix)/'python.exe'),'executable':sys.executable}
    if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(result),encoding='utf-8')
    print(json.dumps(result),flush=True)
    sys.exit(0 if ok else 2)
except Exception as exc:
    print(str(exc),flush=True);sys.exit(2)
