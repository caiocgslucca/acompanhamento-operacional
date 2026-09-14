import hashlib
import hmac
import json
import os
import re
import shutil
import time
import zipfile
from pathlib import Path, PurePosixPath
from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from app.services import config_store as store
from app.services.job_manager import run_source
from app.services.scheduler_service import reset_source_job

router=APIRouter()
ALLOWED={
    'carteira':'Carteira','onda':'Onda','lojas':'Lojas','reab':'Reab',
    'a-extrair':'A Extrair','a_extrair':'A Extrair','aguardando-liberacao':'A Extrair'
}
SUPPORTED={'.xlsx','.xlsm','.csv'}

class PickerResult(BaseModel):
    request_id:str=Field(min_length=32,max_length=32)
    selected_path:str=''
    error:str=''
class SourceError(BaseModel):error:str=Field(min_length=1,max_length=500)
class ReportConfig(BaseModel):
    destination_path:str=Field(min_length=1,max_length=500)
    filename:str=Field(min_length=1,max_length=180)
    schedule:str=Field(min_length=2,max_length=500)
    enabled:bool=False
    filters:str=Field(default='{}',max_length=5000)
class ReportResult(BaseModel):
    status:str=Field(pattern='^(SUCCESS|ERROR|RUNNING)$')
    message:str=Field(default='',max_length=500)

REPORT_MODULES={'carteira':'Carteira','reab':'Reab','producao':'Demanda e Produção'}

def _authorize(key):
    expected=os.getenv('SYNC_API_KEY','').strip()
    if len(expected)<24:raise HTTPException(503,'Sincronização ainda não configurada no servidor.')
    if not key or not hmac.compare_digest(key,expected):raise HTTPException(401,'Chave de sincronização inválida.')

def _safe_members(book):
    members=[];total=0;limit=int(os.getenv('SYNC_MAX_UNCOMPRESSED_MB','500'))*1024*1024
    for item in book.infolist():
        path=PurePosixPath(item.filename)
        if item.is_dir():continue
        if path.is_absolute() or '..' in path.parts or path.suffix.lower() not in SUPPORTED or path.name.startswith('~$'):continue
        total+=item.file_size
        if total>limit:raise HTTPException(413,'Pacote descompactado excede o limite permitido.')
        members.append((item,path))
    if not members:raise HTTPException(422,'O pacote não contém arquivos operacionais compatíveis.')
    return members

@router.get('/api/sync/health')
def sync_health(x_sync_key:str|None=Header(None)):
    _authorize(x_sync_key);return {'ok':True,'service':'operacional-sync'}

@router.get('/api/sync/config')
def sync_config(x_sync_key:str|None=Header(None)):
    _authorize(x_sync_key)
    sources=[]
    for item in store.list_sources():
        name=item['name'].strip()
        origin=(item.get('origin_path') or '').strip()
        if origin and item.get('enabled'):
            sources.append({'id':item['id'],'name':name,'key':f"source-{item['id']}",'path':origin,'schedule':item.get('schedule'),'revision':item.get('sync_revision') or 0})
    return {'ok':True,'sources':sources}

@router.get('/api/report-config/{module}')
def report_config(module:str):
    if module not in REPORT_MODULES:raise HTTPException(404,'Módulo de relatório inválido.')
    current=store.get_report_export(module) or {'module':module,'destination_path':'','filename':f'{module}.pdf','schedule':'{"type":"interval","value":30,"unit":"Minuto(s)"}','enabled':0,'last_run':None,'status':'IDLE','status_message':''}
    return {'ok':True,'data':current}

@router.put('/api/report-config/{module}')
def update_report_config(module:str,payload:ReportConfig):
    if module not in REPORT_MODULES:raise HTTPException(404,'Módulo de relatório inválido.')
    filename=payload.filename.strip()
    if any(char in filename for char in '<>:"/\\|?*'):raise HTTPException(422,'O nome do PDF contém caracteres inválidos.')
    if not filename.lower().endswith('.pdf'):filename+='.pdf'
    try:schedule=json.loads(payload.schedule)
    except json.JSONDecodeError:raise HTTPException(422,'Agendamento inválido.')
    if schedule.get('type') not in ('manual','interval','daily','weekly'):raise HTTPException(422,'Tipo de agendamento inválido.')
    try:
        filters=json.loads(payload.filters or '{}')
        if not isinstance(filters,dict):raise ValueError()
    except (json.JSONDecodeError,ValueError):raise HTTPException(422,'Filtros do PDF inválidos.')
    saved=store.save_report_export(module,{'destination_path':payload.destination_path,'filename':filename,'schedule':json.dumps(schedule,ensure_ascii=False),'enabled':payload.enabled,'filters':json.dumps(filters,ensure_ascii=False)})
    return {'ok':True,'data':saved}

@router.get('/api/sync/reports')
def sync_reports(x_sync_key:str|None=Header(None)):
    _authorize(x_sync_key)
    return {'ok':True,'reports':store.list_report_exports(enabled_only=True)}

@router.get('/api/sync/report/{module}/pdf')
def sync_report_pdf(module:str,x_sync_key:str|None=Header(None)):
    _authorize(x_sync_key)
    if module=='carteira':
        from app.screens.carteira import pdf
        cfg=store.get_report_export(module) or {};f=json.loads(cfg.get('filters') or '{}')
        return pdf(f.get('empresa',[]),f.get('rota',[]),f.get('status',[]))
    elif module=='reab':
        from app.screens.reab import pdf
        cfg=store.get_report_export(module) or {};f=json.loads(cfg.get('filters') or '{}')
        return pdf(f.get('empresa',[]),f.get('rota',[]),f.get('status',[]))
    elif module=='producao':
        from app.screens.producao import pdf
        cfg=store.get_report_export(module) or {};f=json.loads(cfg.get('filters') or '{}')
        return pdf(f.get('empresa',[]),f.get('classe',[]),f.get('data',[]),f.get('turno',[]),f.get('turno_rota',[]))
    else:raise HTTPException(404,'Módulo de relatório inválido.')

@router.post('/api/sync/report/{module}/result')
def sync_report_result(module:str,payload:ReportResult,x_sync_key:str|None=Header(None)):
    _authorize(x_sync_key)
    if module not in REPORT_MODULES:raise HTTPException(404,'Módulo de relatório inválido.')
    store.set_report_export_result(module,payload.status,payload.message,payload.status=='SUCCESS')
    return {'ok':True}

@router.get('/api/sync/picker/request')
def sync_picker_request(x_sync_key:str|None=Header(None)):
    _authorize(x_sync_key);item=store.claim_picker_request()
    if not item:return {'ok':True,'request':None}
    return {'ok':True,'request':{'id':item['id'],'mode':item['mode']}}

@router.post('/api/sync/picker/result')
def sync_picker_result(payload:PickerResult,x_sync_key:str|None=Header(None)):
    _authorize(x_sync_key)
    try:store.complete_picker_request(payload.request_id,payload.selected_path.strip(),payload.error.strip())
    except KeyError:raise HTTPException(404,'Solicitação do seletor não encontrada.')
    return {'ok':True}

@router.post('/api/sync/source-check/{source_id}')
def sync_source_check(source_id:int,x_sync_key:str|None=Header(None)):
    _authorize(x_sync_key)
    try:store.touch_source_check(source_id)
    except KeyError:raise HTTPException(404,'Fonte não encontrada.')
    return {'ok':True,'source_id':source_id}

@router.post('/api/sync/source-start/{source_id}')
def sync_source_start(source_id:int,x_sync_key:str|None=Header(None)):
    _authorize(x_sync_key)
    try:store.mark_source_running(source_id)
    except KeyError:raise HTTPException(404,'Fonte não encontrada.')
    return {'ok':True,'source_id':source_id}

@router.post('/api/sync/source-error/{source_id}')
def sync_source_error(source_id:int,payload:SourceError,x_sync_key:str|None=Header(None)):
    _authorize(x_sync_key)
    try:store.mark_source_error(source_id,payload.error)
    except KeyError:raise HTTPException(404,'Fonte não encontrada.')
    return {'ok':True,'source_id':source_id}

@router.post('/api/sync/source/{source_key}')
def receive_source(source_key:str,archive:UploadFile=File(...),x_sync_key:str|None=Header(None),x_content_sha256:str|None=Header(None)):
    _authorize(x_sync_key);source_id=None;name=ALLOWED.get(source_key.lower())
    if source_key.lower().startswith('source-'):
        try:source_id=int(source_key.split('-',1)[1])
        except ValueError:raise HTTPException(404,'Identificador de fonte inválido.')
        configured=store.get_source(source_id)
        if not configured or not configured.get('enabled'):raise HTTPException(404,'Fonte não encontrada ou desativada.')
        name=configured['name'].strip()
    if not name:raise HTTPException(404,'Fonte não autorizada para sincronização.')
    root=store.DATA_DIR/'cloud_sources'/source_key.lower();incoming=root/'incoming';incoming.mkdir(parents=True,exist_ok=True)
    stamp=f'{int(time.time()*1000)}-{os.getpid()}';package=incoming/f'{stamp}.zip';digest=hashlib.sha256();size=0;limit=int(os.getenv('SYNC_MAX_UPLOAD_MB','250'))*1024*1024
    try:
        with package.open('wb') as output:
            while chunk:=archive.file.read(8*1024*1024):
                size+=len(chunk)
                if size>limit:raise HTTPException(413,'Arquivo excede o limite de envio configurado.')
                digest.update(chunk);output.write(chunk)
        if x_content_sha256 and not hmac.compare_digest(digest.hexdigest(),x_content_sha256.lower()):raise HTTPException(422,'Pacote recebido com assinatura de conteúdo divergente.')
        if not zipfile.is_zipfile(package):raise HTTPException(422,'Pacote ZIP inválido ou incompleto.')
        version=root/f'version-{stamp}';version.mkdir(parents=True)
        with zipfile.ZipFile(package) as book:
            members=_safe_members(book)
            for item,relative in members:
                destination=version.joinpath(*relative.parts);destination.parent.mkdir(parents=True,exist_ok=True)
                with book.open(item) as source,destination.open('wb') as target:shutil.copyfileobj(source,target,8*1024*1024)
        previous=store.get_source(source_id) if source_id else next((s for s in store.list_sources() if s['name'].strip().upper()==name.upper()),None);previous_path=previous['path'] if previous else None
        source_id=store.publish_synced_source(source_id,version) if source_id else store.upsert_synced_source(name,version);run_source(source_id);status=store.get_source(source_id)
        if status.get('status')!='SUCCESS':
            if previous_path:
                store.restore_source_runtime(source_id,previous_path)
                store.set_source_status(source_id,'SUCCESS','Nova carga rejeitada · última versão válida mantida')
            else:store.delete_source(source_id)
            shutil.rmtree(version,ignore_errors=True)
            raise HTTPException(422,f"A carga foi recebida, mas não foi publicada: {status.get('status_message') or 'erro de validação'}")
        reset_source_job(source_id)
        versions=sorted((p for p in root.glob('version-*') if p.is_dir()),key=lambda p:p.stat().st_mtime,reverse=True)
        for old in versions[3:]:shutil.rmtree(old,ignore_errors=True)
        store.logger.info('SYNC_UPLOAD_COMPLETED | fonte=%s | arquivos=%s | bytes=%s | sha256=%s',name,len(members),size,digest.hexdigest())
        return {'ok':True,'source':name,'files':len(members),'bytes':size,'sha256':digest.hexdigest(),'status':status.get('status'),'message':status.get('status_message')}
    finally:
        package.unlink(missing_ok=True);archive.file.close()
