from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_health(): assert client.get('/api/health').json()['status']=='ok'
def test_secure_cloud_sync_publishes_valid_source(monkeypatch,tmp_path):
    import io,zipfile
    from app.services import config_store as store
    from app.services.carteira_engine import invalidate_cache
    key='chave-de-sincronizacao-com-32-caracteres';monkeypatch.setenv('SYNC_API_KEY',key)
    assert client.get('/api/sync/health').status_code==401
    assert client.get('/api/sync/health',headers={'X-Sync-Key':key}).json()['ok'] is True
    source=next((s for s in store.list_sources() if s['name']=='Onda'),None)
    backup={'name':source['name'],'path':source['path'],'schedule':source['schedule'],'enabled':bool(source['enabled'])} if source else None
    payload=io.BytesIO()
    with zipfile.ZipFile(payload,'w') as archive:archive.writestr('Onda_1500.csv','CD_ONDA NUMBER;DS_ONDA VARCHAR2\n10;1 Reab\n20;2 Projeto 14h\n')
    raw=payload.getvalue();import hashlib
    try:
        response=client.post('/api/sync/source/onda',headers={'X-Sync-Key':key,'X-Content-SHA256':hashlib.sha256(raw).hexdigest()},files={'archive':('fonte.zip',raw,'application/zip')})
        assert response.status_code==200 and response.json()['ok'] is True and response.json()['files']==1
        published=next(s for s in store.list_sources() if s['name']=='Onda');assert published['status']=='SUCCESS' and 'cloud_sources' in published['path']
    finally:
        current=next((s for s in store.list_sources() if s['name']=='Onda'),None)
        if backup and current:store.update_source(current['id'],backup)
        elif current:store.delete_source(current['id'])
        invalidate_cache()
def test_professional_login_session(monkeypatch):
    monkeypatch.setenv('APP_USERNAME','caio'); monkeypatch.setenv('APP_PASSWORD','segredo')
    blocked=client.get('/carteira',follow_redirects=False)
    assert blocked.status_code==303 and blocked.headers['location'].startswith('/login')
    assert 'Bem-vindo' in client.get('/login').text
    assert client.post('/login',data={'username':'caio','password':'errada','next_path':'/carteira'}).status_code==401
    logged=client.post('/login',data={'username':'caio','password':'segredo','next_path':'/carteira'},follow_redirects=False)
    assert logged.status_code==303 and logged.headers['location']=='/carteira'
    assert client.get('/carteira').status_code==200
    assert client.get('/api/health').status_code==200
    client.get('/logout')
def test_pages():
    for path in ['/','/carteira','/reab','/producao','/saude','/configuracoes']:
        response=client.get(path); assert response.status_code==200; assert 'Leo Madeiras' in response.text
    for path in ['/recebimento','/expedicao','/inventario','/reversa','/cargas']:
        assert client.get(path).status_code==404
    assert 'Classe</small>' not in client.get('/carteira').text
    assert 'Classe</small>' not in client.get('/reab').text
    production_page=client.get('/producao').text
    assert 'Turno Rota' in production_page and '>Turno<' in production_page

def test_configuration_crud_and_logs():
    from uuid import uuid4
    payload={"name":f"Fonte Teste {uuid4().hex[:8]}","path":"C:\\Teste","schedule":"Manual","enabled":True}
    created=client.post('/api/configuracoes/sources',json=payload)
    assert created.status_code==200
    source_id=created.json()['id']
    assert client.patch(f'/api/configuracoes/sources/{source_id}/toggle',json={"enabled":False}).status_code==200
    payload["path"]="C:\\Teste\\Editado"
    assert client.put(f'/api/configuracoes/sources/{source_id}',json=payload).status_code==200
    assert client.delete(f'/api/configuracoes/sources/{source_id}').status_code==200
    saved=client.post('/api/configuracoes/settings',json={"max_jobs":2,"page_size":100,"cache_seconds":300,"query_timeout":30})
    assert saved.status_code==200 and saved.json()['ok'] is True
    logs=client.get('/api/logs')
    assert logs.status_code==200 and any('SOURCE_CREATED' in line for line in logs.json()['lines'])
    assert client.get('/api/logs/download').status_code==200
    valid_path=client.post('/api/configuracoes/validate-path',json={"path":"./"})
    assert valid_path.status_code==200 and valid_path.json()['is_directory'] is True

def test_configuration_validation():
    invalid=client.post('/api/configuracoes/settings',json={"max_jobs":0,"page_size":100,"cache_seconds":300,"query_timeout":30})
    assert invalid.status_code==422

def test_report_export_configuration(monkeypatch,tmp_path):
    key='chave-de-sincronizacao-com-32-caracteres';monkeypatch.setenv('SYNC_API_KEY',key)
    payload={'destination_path':str(tmp_path),'filename':'carteira_atual.pdf','schedule':'{"type":"interval","value":15,"unit":"Minuto(s)"}','enabled':True}
    saved=client.put('/api/report-config/carteira',json=payload)
    assert saved.status_code==200 and saved.json()['data']['filename']=='carteira_atual.pdf'
    assert client.get('/api/report-config/carteira').json()['data']['enabled']==1
    reports=client.get('/api/sync/reports',headers={'X-Sync-Key':key}).json()['reports']
    assert any(item['module']=='carteira' and item['destination_path']==str(tmp_path) for item in reports)
    payload['enabled']=False
    assert client.put('/api/report-config/carteira',json=payload).status_code==200

def test_native_path_picker_endpoint(monkeypatch,tmp_path):
    from app.screens import configuracoes
    monkeypatch.setattr(configuracoes,'open_native_dialog',lambda mode: str(tmp_path) if mode=='folder' else None)
    selected=client.post('/api/configuracoes/select-path',json={'mode':'folder'})
    assert selected.status_code==200 and selected.json()['selected']==str(tmp_path)
    cancelled=client.post('/api/configuracoes/select-path',json={'mode':'file'})
    assert cancelled.status_code==200 and cancelled.json()['selected'] is None

def test_flexible_schedule_and_force_update(tmp_path):
    (tmp_path/'base.csv').write_text('sku;qtd\n1;10\n',encoding='utf-8')
    payload={"name":"Fonte Job Automático","path":str(tmp_path),"schedule":'{"type":"interval","value":30,"unit":"minuto(s)"}',"enabled":True}
    created=client.post('/api/configuracoes/sources',json=payload)
    assert created.status_code==200
    source_id=created.json()['id']
    from app.services.scheduler_service import next_run_for
    assert next_run_for(source_id) is not None
    run=client.post(f'/api/configuracoes/sources/{source_id}/run')
    assert run.status_code==200
    status=client.get(f'/api/configuracoes/sources/{source_id}/status').json()['data']
    assert status['status']=='SUCCESS' and '1 arquivo(s)' in status['status_message']
    assert client.delete(f'/api/configuracoes/sources/{source_id}').status_code==200

def test_carteira_groups_multiple_files_and_builds_matrices(tmp_path):
    from app.services import config_store as store
    carteira_dir=tmp_path/'carteira'; onda_dir=tmp_path/'onda'; carteira_dir.mkdir(); onda_dir.mkdir()
    (carteira_dir/'filial_1500.csv').write_text('CD_EMPRESA NUMBER;CD_ONDA NUMBER;DS VARCHAR2;CD_CLASSE VARCHAR2;CD_ROTA NUMBER;STATUS_SEPARACAO VARCHAR2;QTD_PENDENTE NUMBER;QT_PRODUTO NUMBER;QT_SEPARADO NUMBER;QT_CANCELADO NUMBER;DATA OFICIAL VARCHAR2\n1500;10;D1;ZCHP;101;PENDENTE;100;100;60;10;04/09/2026\n',encoding='utf-8')
    (carteira_dir/'filial_1502.csv').write_text('CD_EMPRESA NUMBER;CD_ONDA NUMBER;DS VARCHAR2;CD_CLASSE VARCHAR2;CD_ROTA NUMBER;STATUS_SEPARACAO VARCHAR2;QTD_PENDENTE NUMBER;QT_PRODUTO NUMBER;QT_SEPARADO NUMBER;QT_CANCELADO NUMBER;DATA OFICIAL VARCHAR2\n1502;10;D2;ZCOR;102;EM SEPARAÇÃO;50;50;40;0;04/09/2026\n1502;20;MAIOR QUE D7;ZFER;102;PENDENTE;25;25;10;0;05/09/2026\n',encoding='utf-8')
    (onda_dir/'Onda_1500.csv').write_text('CD_ONDA NUMBER;DS_ONDA VARCHAR2\n10;1 Reabastecimento\n',encoding='utf-8')
    (onda_dir/'Onda_1502.csv').write_text('CD_ONDA NUMBER;DS_ONDA VARCHAR2\n20;2 Projeto 14h\n',encoding='utf-8')
    created_onda=None;created_extra=None
    if not any(s['name']=='Onda' for s in store.list_sources()):
        created_onda=store.create_source({'name':'Onda','path':str(onda_dir),'schedule':'{"type":"manual"}','enabled':True})
    sources={s['name']:s for s in store.list_sources() if s['name'] in ('Carteira','Onda')}
    assert set(sources)=={'Carteira','Onda'}
    backups={name:{'name':s['name'],'path':s['path'],'schedule':s['schedule'],'enabled':bool(s['enabled'])} for name,s in sources.items()}
    try:
        store.update_source(sources['Carteira']['id'],{'name':'Carteira','path':str(carteira_dir),'schedule':'{"type":"manual"}','enabled':True})
        store.update_source(sources['Onda']['id'],{'name':'Onda','path':str(onda_dir),'schedule':'{"type":"manual"}','enabled':True})
        result=client.get('/api/carteira/data').json()
        assert result['ok'] is True
        data=result['data']; assert data['meta']['rows']==3 and data['meta']['total_pending']==175
        assert data['matrix_aging']['grand_total']==100 and data['matrix_class']['grand_total']==175
        assert data['matrix_aging']['columns'][:9]==['MAIOR QUE D7','D7','D6','D5','D4','D3','D2','D1','D0']
        assert data['matrix_class']['columns'][:9]==['ZCHP','ZFER','ZFOR','ZLEO','ZMAD','ZMAQ','ZQUI','ZTAB','ZTRI']
        assert [row['label'] for row in data['matrix_class']['rows']]==['1 Reabastecimento','2 Projeto 14h']
        assert set(data['filters']['empresa'])=={'1500','1502'}
        assert set(data['filters']['status'])=={'PENDENTE','EM SEPARAÇÃO'}
        status_filtered=client.get('/api/carteira/data',params={'status':'EM SEPARAÇÃO'}).json()['data']
        assert [row['label'] for row in status_filtered['matrix_class']['rows']]==['1 Reabastecimento']
        filtered=client.get('/api/carteira/data?empresa=1500').json()['data']
        assert filtered['meta']['rows']==1 and filtered['meta']['total_pending']==100
        multi=client.get('/api/carteira/data?empresa=1500&empresa=1502').json()['data']
        assert multi['meta']['rows']==3
        report=client.get('/api/carteira/pdf?empresa=1500')
        assert report.status_code==200 and report.headers['content-type']=='application/pdf' and report.content.startswith(b'%PDF')
        import re
        assert len(re.findall(rb'/Type\s*/Page\b',report.content))==1
        production=client.get('/api/producao/data').json();assert production['ok'] is True
        assert production['data']['totals']['produzir']==175 and production['data']['totals']['separado']==110
        assert production['data']['filters']['data']==['2026-09-04','2026-09-05']
        assert set(production['data']['filters']['empresa'])=={'1500','1502'}
        assert set(production['data']['filters']['turno_rota'])=={'101','102'}
        assert len(production['data']['rows'])==2
        production_filtered=client.get('/api/producao/data',params={'empresa':'1500','turno_rota':'101'}).json()['data']
        assert production_filtered['totals']['produzir']==100
        production_pdf=client.get('/api/producao/pdf',params={'empresa':'1500'})
        assert production_pdf.status_code==200 and production_pdf.content.startswith(b'%PDF')
        assert len(re.findall(rb'/Type\s*/Page\b',production_pdf.content))==1
        extra_dir=tmp_path/'a_extrair';extra_dir.mkdir()
        (extra_dir/'A_Extrair_1500.csv').write_text('CD_EMPRESA;CD_ONDA;DS;CD_CLASSE;CD_ROTA;STATUS_SEPARACAO;QTD_PENDENTE;DS_ONDA\n1500;20;D0;ZCHP;103;AGUARDANDO LIBERAÇÃO;30;2 Projeto 14h\n',encoding='utf-8')
        created_extra=store.create_source({'name':'A Extrair','path':str(extra_dir),'schedule':'{"type":"manual"}','enabled':True})
        from app.services.carteira_engine import invalidate_cache
        invalidate_cache();complemented=client.get('/api/carteira/data').json()['data']
        assert complemented['meta']['rows']==4 and complemented['meta']['total_pending']==205
        assert 'AGUARDANDO LIBERAÇÃO' in complemented['filters']['status']
        waiting=client.get('/api/carteira/data',params={'status':'AGUARDANDO LIBERAÇÃO'}).json()['data']
        assert waiting['matrix_class']['grand_total']==30 and len(waiting['matrix_class']['rows'])==1
        store.delete_source(created_extra);created_extra=None;invalidate_cache()
        # A atualização forçada deve reler o mesmo arquivo depois de linhas
        # serem apagadas, sem reutilizar o DataFrame anterior.
        (carteira_dir/'filial_1502.csv').write_text('CD_EMPRESA NUMBER;CD_ONDA NUMBER;DS VARCHAR2;CD_CLASSE VARCHAR2;CD_ROTA NUMBER;STATUS_SEPARACAO VARCHAR2;QTD_PENDENTE NUMBER\n1502;10;D2;ZCOR;102;SEPARADO;50\n',encoding='utf-8')
        from app.services.job_manager import run_source
        revision_before=client.get('/api/carteira/status').json()['revision']
        run_source(sources['Carteira']['id'])
        assert client.get('/api/carteira/status').json()['revision']>revision_before
        refreshed=client.get('/api/carteira/data').json()['data']
        assert refreshed['meta']['rows']==2 and refreshed['meta']['total_pending']==150
    finally:
        if created_extra:store.delete_source(created_extra)
        store.update_source(sources['Carteira']['id'],backups['Carteira'])
        if created_onda: store.delete_source(created_onda)
        else: store.update_source(sources['Onda']['id'],backups['Onda'])

def test_locked_source_uses_last_valid_local_snapshot(tmp_path,monkeypatch):
    from pathlib import Path
    from app.services.carteira_engine import safe_snapshot
    source=tmp_path/'locked.csv'; source.write_text('a;b\n1;2\n',encoding='utf-8')
    snapshot,stale=safe_snapshot(source,attempts=1)
    assert snapshot.exists() and stale is False
    original_open=Path.open
    def blocked(self,*args,**kwargs):
        if self==source: raise PermissionError(13,'arquivo bloqueado',str(self))
        return original_open(self,*args,**kwargs)
    monkeypatch.setattr(Path,'open',blocked)
    fallback,stale=safe_snapshot(source,attempts=1)
    assert fallback==snapshot and stale is True

def test_concurrent_snapshots_use_independent_temporary_files(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from app.services.carteira_engine import safe_snapshot
    source=tmp_path/'simultaneo.csv';source.write_text('a;b\n1;2\n',encoding='utf-8')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:safe_snapshot(source,attempts=1),range(8)))
    assert all(path.exists() and stale is False for path,stale in results)

def test_reab_uses_fixed_store_rows_and_all_classes(tmp_path):
    from app.services import config_store as store
    from app.services.carteira_engine import invalidate_cache
    carteira_dir=tmp_path/'carteira_reab';lojas_dir=tmp_path/'lojas';carteira_dir.mkdir();lojas_dir.mkdir()
    (carteira_dir/'dados.csv').write_text('CD_EMPRESA;CD_ONDA;DS;CD_CLASSE;CD_ROTA;STATUS_SEPARACAO;QTD_PENDENTE\n1500;10;D1;ZCHP;1001;PENDENTE;100\n1500;10;D2;ZCOR;1003;SEPARADO;50\n1500;20;MAIOR QUE D7;ZFER;1003;PENDENTE;25\n',encoding='utf-8')
    (lojas_dir/'lojas.csv').write_text('Filial;NºLoja;Loja\n1500;1001;SP - Gasometro\n1500;1003;SP - Paes Leme\n1500;1075;SP - Taubate\n',encoding='utf-8')
    carteira=next(s for s in store.list_sources() if s['name']=='Carteira');backup={'name':carteira['name'],'path':carteira['path'],'schedule':carteira['schedule'],'enabled':bool(carteira['enabled'])}
    existing=next((s for s in store.list_sources() if s['name']=='Lojas'),None);lojas_backup={'name':existing['name'],'path':existing['path'],'schedule':existing['schedule'],'enabled':bool(existing['enabled'])} if existing else None
    lojas_id=existing['id'] if existing else store.create_source({'name':'Lojas','path':str(lojas_dir),'schedule':'{"type":"manual"}','enabled':True})
    try:
        store.update_source(carteira['id'],{'name':'Carteira','path':str(carteira_dir),'schedule':'{"type":"manual"}','enabled':True});store.update_source(lojas_id,{'name':'Lojas','path':str(lojas_dir),'schedule':'{"type":"manual"}','enabled':True});invalidate_cache()
        response=client.get('/api/reab/data').json();assert response['ok'] is True;data=response['data']
        assert data['matrix_aging']['row_header']=='Loja Completa'
        assert [r['label'] for r in data['matrix_class']['rows']]==['1001 - SP - Gasometro','1003 - SP - Paes Leme','1075 - SP - Taubate']
        assert data['matrix_aging']['grand_total']==100 and data['matrix_class']['grand_total']==175
        assert data['matrix_class']['rows'][-1]['total']==0
        pending=client.get('/api/reab/data',params={'status':'PENDENTE'}).json()['data']
        assert [r['label'] for r in pending['matrix_class']['rows']]==['1001 - SP - Gasometro','1003 - SP - Paes Leme']
        report=client.get('/api/reab/pdf');assert report.status_code==200 and report.content.startswith(b'%PDF')
    finally:
        store.update_source(carteira['id'],backup)
        if lojas_backup:store.update_source(lojas_id,lojas_backup)
        else:store.delete_source(lojas_id)
        invalidate_cache()

def test_excel_mixed_time_column_is_imported(tmp_path):
    from datetime import time
    from openpyxl import Workbook
    from app.services.carteira_engine import read_file
    path=tmp_path/'onda_mista.xlsx'; book=Workbook(); sheet=book.active
    sheet.append(['CD_ONDA NUMBER','DS_ONDA VARCHAR2','HORARIO'])
    sheet.append([10,'1 Reabastecimento','texto'])
    sheet.append([20,'2 Projeto 14h',time(3,0)])
    book.save(path)
    frame=read_file(path)
    assert frame.height==2 and frame.get_column('HORARIO').to_list()==['texto','03:00:00']

def test_production_dates_are_sorted_chronologically():
    from app.services.producao_engine import _date_key
    values=['01/08/2026','01/09/2026','02/09/2026','03/08/2026']
    assert sorted(values,key=_date_key)==['01/08/2026','03/08/2026','01/09/2026','02/09/2026']
