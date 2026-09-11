import getpass
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TOOLS=ROOT/'tools'
CLOUDFLARED=TOOLS/'cloudflared.exe'
DOWNLOAD_URL='https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe'

def port_ready(port=8000):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=.4):return True
    except OSError:return False

def install_cloudflared():
    if CLOUDFLARED.exists() and CLOUDFLARED.stat().st_size>1_000_000:return
    TOOLS.mkdir(exist_ok=True)
    partial=CLOUDFLARED.with_suffix('.part')
    print('Baixando o conector seguro Cloudflare...')
    try:
        urllib.request.urlretrieve(DOWNLOAD_URL,partial)
        partial.replace(CLOUDFLARED)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError('Não foi possível baixar cloudflared.exe. A rede da empresa pode ter bloqueado o download.') from exc

def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]

def wait_server(process,port):
    for _ in range(120):
        if process.poll() is not None:raise RuntimeError('O servidor encerrou durante a inicialização.')
        if port_ready(port):return
        time.sleep(.25)
    raise RuntimeError(f'O servidor não respondeu na porta {port}.')

def open_when_public(url):
    health=url+'/api/health'
    for _ in range(60):
        try:
            with urllib.request.urlopen(health,timeout=3) as response:
                if response.status==200:
                    webbrowser.open(url+'/carteira');return
        except Exception:time.sleep(1)
    print('O endereço foi criado, mas a rede demorou para liberá-lo. Abra o link salvo em ENDERECO_ONLINE.txt.')

def main():
    if os.name!='nt':raise RuntimeError('Este iniciador é destinado ao Windows.')
    port=8000 if not port_ready(8000) else free_port()
    username=input('Usuário de acesso [administrador]: ').strip() or 'administrador'
    password=getpass.getpass('Crie uma senha de acesso (mínimo 8 caracteres): ').strip()
    if len(password)<8:raise RuntimeError('A senha precisa ter no mínimo 8 caracteres.')
    confirmation=getpass.getpass('Confirme a senha: ').strip()
    if password!=confirmation:raise RuntimeError('As senhas não conferem.')
    install_cloudflared()
    env=os.environ.copy();env['APP_USERNAME']=username;env['APP_PASSWORD']=password;env['APP_HOST']='127.0.0.1';env['PORT']=str(port)
    server=subprocess.Popen([sys.executable,'run.py'],cwd=ROOT,env=env)
    tunnel=None
    try:
        wait_server(server,port)
        reconnects=0
        while server.poll() is None:
            tunnel=subprocess.Popen([str(CLOUDFLARED),'tunnel','--url',f'http://127.0.0.1:{port}','--no-autoupdate'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
            opened=False;assert tunnel.stdout is not None
            for line in tunnel.stdout:
                match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',line,re.I)
                if match and not opened:
                    url=match.group(0);(ROOT/'ENDERECO_ONLINE.txt').write_text(url+'/carteira\n',encoding='utf-8')
                    print('\n'+'='*70);print('ENDEREÇO ONLINE PARA CELULAR E NOTEBOOK:');print(url+'/carteira');print(f'Usuário: {username}');print('Use a senha informada na inicialização.');print('Mantenha esta janela aberta. Pressione CTRL+C para encerrar.');print('='*70+'\n')
                    threading.Thread(target=open_when_public,args=(url,),daemon=True).start();opened=True;reconnects=0
                elif 'ERR' in line.upper():print(line.rstrip())
            if server.poll() is not None:break
            reconnects+=1;delay=min(3*reconnects,30)
            print(f'Túnel desconectado. Reconectando automaticamente em {delay} segundos...');time.sleep(delay)
    finally:
        if tunnel and tunnel.poll() is None:tunnel.terminate()
        if server.poll() is None:server.terminate()

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nAcesso online encerrado.')
    except Exception as exc:
        print(f'\nERRO: {exc}')
        input('Pressione ENTER para fechar...')
        raise SystemExit(1)
