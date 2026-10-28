import _bootstrap
import argparse
import threading,urllib.request,webbrowser
from src.dashboard.server import serve
if __name__=='__main__':
    p=argparse.ArgumentParser(description='Launch the local QuantumFlow dashboard');p.add_argument('--port',type=int,default=8765);p.add_argument('--open',dest='open_browser',action='store_true');a=p.parse_args()
    if not 1024<=a.port<=65535:raise SystemExit('Choose a port from 1024 to 65535')
    if a.open_browser:
        url=f'http://127.0.0.1:{a.port}'
        try:
            with urllib.request.urlopen(url,timeout=3) as response:existing=response.read(4096)
            if b'QuantumFlow BLR' in existing:
                webbrowser.open_new_tab(url);raise SystemExit(0)
        except OSError:pass
        threading.Timer(1.2,lambda:webbrowser.open_new_tab(url)).start()
    serve(_bootstrap.ROOT,a.port)
