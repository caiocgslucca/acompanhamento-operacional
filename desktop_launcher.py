import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

cpu_count=os.cpu_count() or 2
os.environ.setdefault('POLARS_MAX_THREADS',str(max(1,min(4,cpu_count//2))))

def set_low_priority():
    if sys.platform!='win32':return
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x00004000)
    except Exception:pass

def port_ready(host='127.0.0.1',port=8000):
    try:
        with socket.create_connection((host,port),timeout=.4):return True
    except OSError:return False

def open_when_ready():
    for _ in range(80):
        if port_ready():
            webbrowser.open('http://127.0.0.1:8000');return
        time.sleep(.25)

def main():
    set_low_priority()
    executable_dir=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
    os.chdir(executable_dir)
    if port_ready():
        webbrowser.open('http://127.0.0.1:8000');return
    threading.Thread(target=open_when_ready,daemon=True).start()
    import uvicorn
    from app.main import app
    print('Acesso local: http://127.0.0.1:8000/carteira')
    try:
        lan_ip=socket.gethostbyname(socket.gethostname())
        if lan_ip and not lan_ip.startswith('127.'):
            print(f'Acesso na rede local: http://{lan_ip}:8000/carteira')
    except OSError:pass
    uvicorn.run(app,host='0.0.0.0',port=8000,log_level='info',access_log=False)

if __name__=='__main__':main()
