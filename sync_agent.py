import hashlib
import json
import logging
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parent
CONFIG=ROOT/'sync_config.json';STATE=ROOT/'data'/'sync_state.json';LOG=ROOT/'logs'/'sincronizador.log'
SUPPORTED={'.xlsx','.xlsm','.csv'}
REMOTE_KEYS={'CARTEIRA':'carteira','ONDA':'onda','LOJAS':'lojas','LOJA':'lojas','REAB':'reab','A EXTRAIR':'a-extrair','A_EXTRAIR':'a-extrair','AGUARDANDO LIBERACAO':'a-extrair'}

def native_select(mode):
    if os.name!='nt':return ''
    owner="$o=New-Object System.Windows.Forms.Form;$o.ShowInTaskbar=$false;$o.TopMost=$true;$o.StartPosition='CenterScreen';$o.Size=New-Object System.Drawing.Size -ArgumentList 1,1;$o.Opacity=0.01;$o.Show();$o.Activate();$o.BringToFront();"
    if mode=='folder':
        script="Add-Type -AssemblyName System.Windows.Forms;Add-Type -AssemblyName System.Drawing;"+owner+"$d=New-Object System.Windows.Forms.FolderBrowserDialog;$d.Description='Selecionar ou criar pasta';$d.ShowNewFolderButton=$true;if($d.ShowDialog($o) -eq 'OK'){[Console]::OutputEncoding=[Text.Encoding]::UTF8;Write-Output $d.SelectedPath};$d.Dispose();$o.Close();$o.Dispose()"
    else:
        script="Add-Type -AssemblyName System.Windows.Forms;Add-Type -AssemblyName System.Drawing;"+owner+"$d=New-Object System.Windows.Forms.OpenFileDialog;$d.Title='Selecionar arquivo de dados';$d.Filter='Planilhas (*.xlsx;*.xlsm;*.csv)|*.xlsx;*.xlsm;*.csv|Todos os arquivos (*.*)|*.*';if($d.ShowDialog($o) -eq 'OK'){[Console]::OutputEncoding=[Text.Encoding]::UTF8;Write-Output $d.FileName};$d.Dispose();$o.Close();$o.Dispose()"
    result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-STA','-Command',script],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
    return result.stdout.strip().splitlines()[-1].strip() if result.returncode==0 and result.stdout.strip() else ''

def remote_picker_worker(config,log):
    server=str(config.get('server_url','')).strip().rstrip('/');key=str(config.get('api_key','')).strip()
    headers={'X-Sync-Key':key}
    log.info('SELETOR_REMOTO_ATIVO | consulta_segundos=1')
    while True:
        try:
            with httpx.Client(timeout=30,follow_redirects=True) as client:
                response=client.get(f'{server}/api/sync/picker/request',headers=headers);response.raise_for_status()
                request=response.json().get('request')
                if request:
                    request_id=request['id'];mode=request['mode'];log.info('SELETOR_SOLICITADO | id=%s | mode=%s',request_id,mode)
                    try:
                        selected=native_select(mode)
                        payload={'request_id':request_id,'selected_path':selected,'error':''}
                    except Exception as exc:
                        log.exception('SELETOR_LOCAL_FALHOU | id=%s | erro=%s',request_id,exc)
                        payload={'request_id':request_id,'selected_path':'','error':str(exc)}
                    result=client.post(f'{server}/api/sync/picker/result',headers=headers,json=payload);result.raise_for_status()
        except Exception as exc:
            log.warning('SELETOR_REMOTO_INDISPONIVEL | erro=%s',exc)
            time.sleep(5);continue
        time.sleep(1)

def process_lock():
    path=ROOT/'data'/'sync_agent.lock';path.parent.mkdir(parents=True,exist_ok=True);handle=path.open('a+b')
    try:
        if os.name=='nt':
            import msvcrt
            handle.seek(0);handle.write(b'1');handle.flush();handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except (OSError,IOError):handle.close();raise RuntimeError('O sincronizador já está em execução neste computador.')
    return handle

def clean(value):return ' '.join(unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode().upper().replace('_',' ').split())

def logger():
    LOG.parent.mkdir(parents=True,exist_ok=True);log=logging.getLogger('operacional-sync')
    if not log.handlers:
        log.setLevel(logging.INFO);formatter=logging.Formatter('%(asctime)s | %(levelname)s | %(message)s','%d/%m/%Y %H:%M:%S');stream=logging.StreamHandler();stream.setFormatter(formatter);file=logging.FileHandler(LOG,encoding='utf-8');file.setFormatter(formatter);log.addHandler(stream);log.addHandler(file)
    return log

def load_json(path,default):
    try:return json.loads(path.read_text('utf-8'))
    except (FileNotFoundError,json.JSONDecodeError):return default

def source_files(path_text):
    path=Path(path_text)
    if not path.exists():return []
    files=[path] if path.is_file() else sorted(p for p in path.rglob('*') if p.is_file())
    return [p for p in files if p.suffix.lower() in SUPPORTED and not p.name.startswith('~$')]

def database_sources():
    database=ROOT/'data'/'operacional.db'
    if not database.exists():return {}
    with sqlite3.connect(database) as connection:
        rows=connection.execute('SELECT name,path FROM sources WHERE enabled=1').fetchall()
    return {name:path for name,path in rows if source_files(path)}

def configured_sources(config,client,server,key,log):
    try:
        response=client.get(f'{server}/api/sync/config',headers={'X-Sync-Key':key});response.raise_for_status()
        remote=response.json().get('sources') or []
        if remote:
            return {item['name']:{'path':item['path'],'revision':item.get('revision',0),'source_id':item.get('id'),'schedule':item.get('schedule')} for item in remote}
    except Exception as exc:
        log.warning('CONFIG_REMOTA_INDISPONIVEL | usando configuração local | erro=%s',exc)
    explicit=config.get('sources') or database_sources()
    return {name:{'path':path,'revision':0} for name,path in explicit.items()}

def configured_reports(client,server,key,log):
    try:
        response=client.get(f'{server}/api/sync/reports',headers={'X-Sync-Key':key});response.raise_for_status()
        return response.json().get('reports') or []
    except Exception as exc:
        log.warning('CONFIG_RELATORIOS_INDISPONIVEL | erro=%s',exc);return []

def fingerprint(files,base):
    digest=hashlib.sha256()
    for path in files:
        relative=path.name if base.is_file() else path.relative_to(base).as_posix();digest.update(relative.encode('utf-8'))
        with path.open('rb') as source:
            while block:=source.read(8*1024*1024):digest.update(block)
    return digest.hexdigest()

def make_archive(files,base):
    handle=tempfile.NamedTemporaryFile(prefix='operacional-sync-',suffix='.zip',delete=False);handle.close();archive=Path(handle.name)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as book:
        for path in files:book.write(path,path.name if base.is_file() else path.relative_to(base).as_posix())
    return archive

def schedule_due(source,state):
    remote=f"source-{source.get('source_id')}" if source.get('source_id') else clean(source.get('path'))
    meta=(state.get('_schedule_meta') or {}).get(remote)
    revision=int(source.get('revision') or 0)
    if not meta or int(meta.get('revision',-1))!=revision:return True,remote
    try:cfg=json.loads(source.get('schedule') or '{}')
    except (TypeError,json.JSONDecodeError):cfg={}
    kind=cfg.get('type','manual');now=datetime.now()
    try:last=datetime.fromisoformat(meta['checked_at'])
    except (KeyError,TypeError,ValueError):return True,remote
    if kind=='manual':return False,remote
    if kind=='interval':
        value=max(1,int(cfg.get('value',1)));unit=str(cfg.get('unit','minuto(s)'))
        return now>=last+(timedelta(minutes=value) if unit.startswith('minuto') else timedelta(hours=value)),remote
    try:hour,minute=map(int,str(cfg.get('time','06:00')).split(':'))
    except ValueError:hour,minute=6,0
    scheduled=now.replace(hour=hour,minute=minute,second=0,microsecond=0)
    if kind=='daily':return now>=scheduled and last<scheduled,remote
    if kind=='weekly':
        days={'seg':0,'ter':1,'qua':2,'qui':3,'sex':4,'sab':5,'dom':6}
        allowed={days[d] for d in str(cfg.get('days','')).split(',') if d in days}
        return now.weekday() in allowed and now>=scheduled and last<scheduled,remote
    return False,remote

def mark_schedule_checked(state,remote,revision):
    state.setdefault('_schedule_meta',{})[remote]={'checked_at':datetime.now().isoformat(timespec='seconds'),'revision':int(revision or 0)}

def report_schedule_due(report,state):
    """Agenda exclusiva dos PDFs. A primeira ativação inicia a contagem sem baixar tudo de uma vez."""
    remote=f"report::{report['module']}"
    try:cfg=json.loads(report.get('schedule') or '{}')
    except (TypeError,json.JSONDecodeError):cfg={}
    meta=(state.get('_report_schedule_meta') or {}).get(remote)
    last_text=(meta or {}).get('checked_at') or report.get('last_run')
    now=datetime.now().astimezone()
    if not last_text:
        state.setdefault('_report_schedule_meta',{})[remote]={'checked_at':now.isoformat(timespec='seconds')}
        save_state(state);return False,remote
    try:
        last=datetime.fromisoformat(str(last_text).replace('Z','+00:00'))
        if last.tzinfo is None:last=last.replace(tzinfo=now.tzinfo)
        last=last.astimezone(now.tzinfo)
    except (TypeError,ValueError):last=now
    kind=cfg.get('type','interval')
    if kind=='interval':
        value=max(1,int(cfg.get('value',1)));unit=str(cfg.get('unit','minuto(s)')).strip().lower()
        return now>=last+(timedelta(minutes=value) if unit.startswith('minuto') else timedelta(hours=value)),remote
    try:hour,minute=map(int,str(cfg.get('time','06:00')).split(':'))
    except ValueError:hour,minute=6,0
    scheduled=now.replace(hour=hour,minute=minute,second=0,microsecond=0)
    if kind=='daily':return now>=scheduled and last<scheduled,remote
    if kind=='weekly':
        days={'seg':0,'ter':1,'qua':2,'qui':3,'sex':4,'sab':5,'dom':6};allowed={days[d] for d in str(cfg.get('days','')).split(',') if d in days}
        return now.weekday() in allowed and now>=scheduled and last<scheduled,remote
    return False,remote

def mark_report_checked(state,remote):
    state.setdefault('_report_schedule_meta',{})[remote]={'checked_at':datetime.now().astimezone().isoformat(timespec='seconds')}

def optional_sync_event(client,url,headers,log,event,json_body=None):
    """Eventos de estado não podem impedir o envio durante uma troca de versão."""
    response=client.post(url,headers=headers,json=json_body)
    if response.status_code==404:
        log.warning('SERVIDOR_AGUARDANDO_NOVA_VERSAO | evento=%s | envio_continuara',event);return False
    response.raise_for_status();return True

def send(client,server,key,name,path_text,previous,log,revision=0,source_id=None):
    remote=f'source-{source_id}' if source_id else REMOTE_KEYS.get(clean(name))
    if not remote:return previous
    base=Path(path_text);files=source_files(path_text)
    if not files:raise ValueError(f'Caminho não encontrado, vazio ou sem arquivos compatíveis: {path_text}')
    current=fingerprint(files,base);state_key=f'{current}:{revision}'
    if previous.get(remote)==state_key:log.info('ARQUIVOS_SEM_ALTERACAO | fonte=%s | reenviando_por_agendamento=true',name)
    archive=make_archive(files,base)
    try:
        package_hash=hashlib.sha256(archive.read_bytes()).hexdigest();log.info('ENVIO_INICIADO | fonte=%s | arquivos=%s | tamanho_mb=%.1f',name,len(files),archive.stat().st_size/1048576)
        with archive.open('rb') as payload:
            response=client.post(f'{server}/api/sync/source/{remote}',headers={'X-Sync-Key':key,'X-Content-SHA256':package_hash},files={'archive':('fonte.zip',payload,'application/zip')})
        if response.is_error:
            try:detail=response.json().get('detail') or response.text
            except Exception:detail=response.text
            raise RuntimeError(f'Railway rejeitou a carga ({response.status_code}): {detail}')
        body=response.json()
        if not body.get('ok'):raise RuntimeError(body.get('message') or 'Servidor recusou a publicação.')
        previous[remote]=state_key;log.info('ENVIO_CONCLUIDO | fonte=%s | arquivos=%s | %s',name,body.get('files'),body.get('message','publicado'))
        return previous
    finally:archive.unlink(missing_ok=True)

def save_state(state):
    STATE.parent.mkdir(parents=True,exist_ok=True);temporary=STATE.with_suffix('.tmp');temporary.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temporary,STATE)

def export_report(client,server,key,report,state,log):
    module=report['module'];due,remote=report_schedule_due(report,state)
    if not due:
        log.info('PDF_AGUARDANDO_JANELA | modulo=%s | agendamento=%s',module,report.get('schedule'));return state
    destination=Path(report['destination_path']);destination.mkdir(parents=True,exist_ok=True)
    filename=Path(report['filename']).name
    if not filename.lower().endswith('.pdf'):filename+='.pdf'
    target=destination/filename;temporary=destination/f'.{filename}.novo'
    headers={'X-Sync-Key':key}
    try:
        client.post(f'{server}/api/sync/report/{module}/result',headers=headers,json={'status':'RUNNING','message':'Gerando PDF'}).raise_for_status()
        log.info('PDF_GERACAO_INICIADA | modulo=%s | destino=%s',module,target)
        with client.stream('GET',f'{server}/api/sync/report/{module}/pdf',headers=headers) as response:
            response.raise_for_status()
            with temporary.open('wb') as output:
                for chunk in response.iter_bytes(1024*1024):output.write(chunk)
        if temporary.stat().st_size<4 or temporary.read_bytes()[:4]!=b'%PDF':raise ValueError('O servidor não retornou um PDF válido.')
        os.replace(temporary,target)
        mark_report_checked(state,remote);save_state(state)
        message=f'PDF substituído com sucesso: {target}'
        client.post(f'{server}/api/sync/report/{module}/result',headers=headers,json={'status':'SUCCESS','message':message}).raise_for_status()
        log.info('PDF_GERACAO_CONCLUIDA | modulo=%s | arquivo=%s | tamanho_kb=%.1f',module,target,target.stat().st_size/1024)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        mark_report_checked(state,remote);save_state(state)
        try:client.post(f'{server}/api/sync/report/{module}/result',headers=headers,json={'status':'ERROR','message':str(exc)[:500]}).raise_for_status()
        except Exception:pass
        log.exception('PDF_GERACAO_FALHOU | modulo=%s | erro=%s',module,exc)
    return state

def run_once(config,log):
    server=str(config.get('server_url','')).strip().rstrip('/');key=str(config.get('api_key','')).strip()
    if not server.startswith('https://'):raise ValueError('Informe no sync_config.json o endereço HTTPS do Railway.')
    if len(key)<24:raise ValueError('A SYNC_API_KEY precisa ter pelo menos 24 caracteres.')
    state=load_json(STATE,{})
    failures=[]
    with httpx.Client(timeout=httpx.Timeout(600,connect=30),follow_redirects=True) as client:
        health=client.get(f'{server}/api/sync/health',headers={'X-Sync-Key':key});health.raise_for_status()
        sources=configured_sources(config,client,server,key,log)
        if not sources:raise ValueError('Nenhuma fonte ativa foi cadastrada na tela Configurações do sistema.')
        # Um único PDF por ciclo. Os demais permanecem na fila para a próxima consulta.
        for report in configured_reports(client,server,key,log):
            due,_=report_schedule_due(report,state)
            if due:
                state=export_report(client,server,key,report,state,log);break
        for name,source in sources.items():
            due,remote=schedule_due(source,state)
            if not due:
                log.info('FONTE_AGUARDANDO_JANELA | fonte=%s | agendamento=%s',name,source.get('schedule'));continue
            try:
                if source.get('source_id'):
                    optional_sync_event(client,f"{server}/api/sync/source-start/{source['source_id']}",{'X-Sync-Key':key},log,'inicio')
                state=send(client,server,key,name,source['path'],state,log,source.get('revision',0),source.get('source_id'))
                if source.get('source_id'):
                    optional_sync_event(client,f"{server}/api/sync/source-check/{source['source_id']}",{'X-Sync-Key':key},log,'conclusao')
                mark_schedule_checked(state,remote,source.get('revision',0));save_state(state)
            except Exception as exc:
                if source.get('source_id'):
                    try:optional_sync_event(client,f"{server}/api/sync/source-error/{source['source_id']}",{'X-Sync-Key':key},log,'erro',{'error':str(exc)[:500]})
                    except Exception:pass
                failures.append(f'{name}: {exc}');log.exception('ENVIO_FALHOU | fonte=%s | erro=%s',name,exc)
    if failures:raise RuntimeError('Falha em uma ou mais fontes: '+'; '.join(failures))

def main():
    lock=process_lock();log=logger();config=load_json(CONFIG,{})
    if not config:raise FileNotFoundError('Execute primeiro CONFIGURAR_SINCRONIZADOR.bat.')
    interval=max(1,int(config.get('interval_minutes',5)));once='--once' in sys.argv
    if not once:threading.Thread(target=remote_picker_worker,args=(config,log),name='operacional-picker',daemon=True).start()
    log.info('SINCRONIZADOR_INICIADO | consulta_agendamentos_minutos=%s | modo=%s',interval,'único' if once else 'contínuo')
    while True:
        try:run_once(config,log)
        except Exception as exc:
            log.exception('CICLO_FALHOU | erro=%s',exc)
            if once:raise
        if once:return
        poll_seconds=min(interval*60,30)
        log.info('PROXIMA_CONSULTA_DE_AGENDAMENTOS | segundos=%s',poll_seconds);time.sleep(poll_seconds)

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:logger().info('SINCRONIZADOR_ENCERRADO')
    except Exception as exc:logger().error('INICIALIZACAO_FALHOU | erro=%s',exc);raise SystemExit(1)
