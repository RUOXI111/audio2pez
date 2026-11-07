"""Exercise desktop callbacks with real workers; no input automation library needed."""
import json,sys,traceback
from pathlib import Path
import tkinter as tk
import desktop_app as ui
ROOT=Path(__file__).resolve().parent
ui.SETTINGS=ROOT/'.desktop'/'ui_test_settings.json'
errors=[]
ui.messagebox.showerror=lambda title,text,**kw:errors.append((title,text))
ui.messagebox.askyesno=lambda *a,**k:True
root=tk.Tk();app=ui.DesktopApp(root)
phase=0;failed=[]
for k,v in ui.DEFAULTS.items():app.vars[k].set(v)
for k,v in {'audio':str(ROOT/'test_song.wav'),'title':'GUI integration','mode':'standard','bpm':'128','chorus':'10-20','preview_start':'10','preview_duration':'5','output_dir':str(ROOT/'output'/'_desktop_ui_tests')}.items():app.vars[k].set(v)
app._mode_changed()
def fail(exc):
    failed.append(str(exc));traceback.print_exc();app._cancel();root.after(1000,root.destroy)
def step():
    global phase
    try:
        if phase==0:
            app._generate();assert app.running,errors
            phase=1
        elif phase==1 and not app.running:
            assert app.result,errors
            assert len(app.chart_tree.get_children())==1
            assert Path(app.result['preview']).is_file()
            from PIL import ImageGrab
            root.update_idletasks()
            x,y=root.winfo_rootx(),root.winfo_rooty()
            ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save(ROOT/'.desktop'/'desktop_preview.png')
            print('PASS UI generation and result display',flush=True)
            app.vars['audio'].set(str(ROOT/'songs'/'小半.ogg'));app.vars['mode'].set('drums');app._mode_changed();app._generate()
            assert app.running
            root.after(400,app._cancel);phase=2
        elif phase==2 and not app.running:
            assert app.cancel_event.is_set() and app.result is None
            print('PASS cancel worker tree',flush=True)
            app.vars['audio'].set(str(ROOT/'test_song.wav'));app.vars['mode'].set('standard');app.vars['preview_start'].set('999');app._mode_changed();app._generate();phase=3
        elif phase==3 and not app.running:
            assert app.result is None and errors
            print('PASS worker error and controls restored',flush=True)
            root.destroy();return
        root.after(100,step)
    except Exception as exc:fail(exc)
def timeout():
    failed.append('UI integration timed out');app._cancel();root.after(1000,root.destroy)
root.after(200,step);root.after(90000,timeout);root.mainloop()
if failed:print(failed);sys.exit(1)
print('UI TESTS PASSED')
