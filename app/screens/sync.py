import hashlib
import hmac
import os
import shutil
import time
import zipfile
from pathlib import Path, PurePosixPath
from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from app.services import config_store as store
from app.services.job_manager import run_source

router=APIRouter()
ALLOWED={
    'carteira':'Carteira','onda':'Onda','lojas':'Lojas','reab':'Reab',
    'a-extrair':'A Extrair','a_extrair':'A Extrair','aguardando-liberacao':'A Extrair'
}
SUPPORTED={'.xlsx','.xlsm','.csv'}

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

@router.post('/api/sync/source/{source_key}')
def receive_source(source_key:str,archive:UploadFile=File(...),x_sync_key:str|None=Header(None),x_content_sha256:str|None=Header(None)):
    _authorize(x_sync_key);name=ALLOWED.get(source_key.lower())
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
        previous=next((s for s in store.list_sources() if s['name'].strip().upper()==name.upper()),None);previous_path=previous['path'] if previous else None
        source_id=store.upsert_synced_source(name,version);run_source(source_id);status=store.get_source(source_id)
        if status.get('status')!='SUCCESS':
            if previous_path:
                store.update_source(source_id,{'name':previous['name'],'path':previous_path,'schedule':previous['schedule'],'enabled':bool(previous['enabled'])})
                store.set_source_status(source_id,'SUCCESS','Nova carga rejeitada · última versão válida mantida')
            else:store.delete_source(source_id)
            shutil.rmtree(version,ignore_errors=True)
            raise HTTPException(422,f"A carga foi recebida, mas não foi publicada: {status.get('status_message') or 'erro de validação'}")
        versions=sorted((p for p in root.glob('version-*') if p.is_dir()),key=lambda p:p.stat().st_mtime,reverse=True)
        for old in versions[3:]:shutil.rmtree(old,ignore_errors=True)
        store.logger.info('SYNC_UPLOAD_COMPLETED | fonte=%s | arquivos=%s | bytes=%s | sha256=%s',name,len(members),size,digest.hexdigest())
        return {'ok':True,'source':name,'files':len(members),'bytes':size,'sha256':digest.hexdigest(),'status':status.get('status'),'message':status.get('status_message')}
    finally:
        package.unlink(missing_ok=True);archive.file.close()
