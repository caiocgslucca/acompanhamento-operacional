import time
from datetime import datetime
from pathlib import Path
from threading import Lock
from app.services import config_store as store

_running=set(); _lock=Lock(); _data_revision=0
SUPPORTED={'.xlsx','.xlsm','.xlsb','.xls','.csv','.parquet'}

def run_source(source_id:int):
    global _data_revision
    with _lock:
        if source_id in _running:
            store.logger.warning('JOB_IGNORED | source_id=%s | motivo=execução já em andamento',source_id); return
        _running.add(source_id)
    started=time.perf_counter()
    try:
        source=store.get_source(source_id)
        if not source: raise FileNotFoundError('Fonte não cadastrada')
        path=Path(source['path'])
        store.set_source_status(source_id,'RUNNING','Atualização em andamento')
        store.logger.info('JOB_STARTED | id=%s | fonte=%s | caminho=%s',source_id,source['name'],path)
        if not path.exists(): raise FileNotFoundError(f'Caminho não encontrado: {path}')
        files=[path] if path.is_file() else sorted(p for p in path.rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED and not p.name.startswith('~$'))
        if not files: raise FileNotFoundError(f'Nenhum arquivo compatível encontrado em: {path}')
        store.logger.info('SOURCE_DISCOVERY_REFRESH | id=%s | fonte=%s | arquivos_atuais=%s',source_id,source['name'],len(files))
        analytical=source['name'].strip().upper() in ('CARTEIRA','ONDA','LOJAS','LOJA','FILIAIS','FILIAL','REAB','LOJAS_REAB','CADASTRO_LOJAS','A_EXTRAIR','A EXTRAIR','AGUARDANDO_LIBERACAO') or 'A_EXTRAIR' in path.name.upper()
        if analytical:
            from app.services.carteira_engine import invalidate_cache, load_source
            invalidate_cache(source['name'])
            frame,_,used_previous_snapshot=load_source(source['name'],force=True)
            if used_previous_snapshot:
                raise RuntimeError('A fonte foi localizada, mas o arquivo atual estava bloqueado. A versão anterior foi mantida e a atualização não foi publicada.')
            with _lock:_data_revision+=1
            store.logger.info('SOURCE_DATA_PUBLISHED | id=%s | fonte=%s | linhas=%s',source_id,source['name'],frame.height)
        total_bytes=sum(p.stat().st_size for p in files)
        elapsed=round(time.perf_counter()-started,3)
        message=f'{len(files)} arquivo(s) localizado(s) · {total_bytes/1048576:.1f} MB · {elapsed:.2f}s'
        store.set_source_status(source_id,'SUCCESS',message)
        store.logger.info('JOB_COMPLETED | id=%s | fonte=%s | arquivos=%s | bytes=%s | segundos=%s',source_id,source['name'],len(files),total_bytes,elapsed)
    except Exception as exc:
        store.set_source_status(source_id,'ERROR',str(exc))
        store.logger.exception('JOB_FAILED | id=%s | erro=%s',source_id,exc)
    finally:
        with _lock: _running.discard(source_id)

def status(source_id:int):
    source=store.get_source(source_id)
    if not source: return None
    return {k:source.get(k) for k in ('id','status','status_message','last_run')}

def data_revision():return _data_revision
