"""Health check after setup; no user song access or network."""
import sys
def main():
    import numpy as np,librosa,numba,scipy,soundfile as sf,av,PIL,tkinter as tk
    import desktop_worker,desktop_drums,desktop_app
    if sys.version_info[:2]!=(3,12) or sys.maxsize<=2**32:raise RuntimeError('Need Python3.12 x64')
    root=tk.Tk();root.withdraw();root.update();root.destroy()
    y=np.zeros(22050*8,dtype=np.float32)
    pulse=np.exp(-np.arange(512)/65).astype(np.float32)
    for pos in range(2205,len(y)-512,11025):y[pos:pos+512]+=pulse
    tempo,beats=librosa.beat.beat_track(y=y,sr=22050)
    if not len(beats):raise RuntimeError('Beat tracker returned no beats')
    assert 'OGG' in sf.available_formats()
    av.Codec('aac','r')
    print('HEALTH_OK Python='+sys.version.split()[0]+' NumPy='+np.__version__+' librosa='+librosa.__version__+' PyAV='+av.__version__+' Tk='+str(tk.TkVersion),flush=True)
if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    main()
