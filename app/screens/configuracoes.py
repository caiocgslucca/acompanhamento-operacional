import hashlib
import json
import os
import sqlite3
from html import escape
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from app.services.ui import layout
from app.services import config_store as store
from app.services import job_manager
from app.services.scheduler_service import refresh_jobs, next_run_for
from app.services.native_dialog import select_path as open_native_dialog, NativeDialogError

router=APIRouter()

class SourcePayload(BaseModel):
    name: str = Field(min_length=2,max_length=80)
    path: str = Field(min_length=2,max_length=500)
    schedule: str = Field(min_length=2,max_length=100)
    enabled: bool = True
class TogglePayload(BaseModel): enabled: bool
class PathPayload(BaseModel): path: str = Field(min_length=2,max_length=500)
class PickerPayload(BaseModel): mode: str = Field(pattern='^(folder|file)$')
class SettingsPayload(BaseModel):
    max_jobs: int = Field(ge=1,le=16)
    page_size: int = Field(ge=50,le=500)
    cache_seconds: int = Field(ge=0,le=86400)
    query_timeout: int = Field(ge=5,le=600)

def source_row(item):
    checked='checked' if item['enabled'] else ''
    esc=lambda value: str(value).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
    name,path,schedule=esc(item['name']),esc(item.get('origin_path') or item['path']),esc(item['schedule'])
    try:
        cfg=json.loads(item['schedule']); kind=cfg.get('type','manual')
        if kind=='interval': schedule_label=f"A cada {cfg.get('value',1)} {cfg.get('unit','hora(s)')}"
        elif kind=='daily': schedule_label=f"Diariamente às {cfg.get('time','06:00')}"
        elif kind=='weekly': schedule_label=f"Semanal · {cfg.get('days','seg')} · {cfg.get('time','06:00')}"
        else: schedule_label='Somente manual'
    except Exception: schedule_label=item['schedule']
    status=item.get('status') or 'IDLE'; status_label={'SUCCESS':'Atualizado','RUNNING':'Atualizando…','ERROR':'Falha','IDLE':'Nunca executado'}.get(status,status)
    def dt(value):
        if not value:return '—'
        try:return __import__('datetime').datetime.fromisoformat(value).strftime('%d/%m/%Y %H:%M')
        except Exception:return str(value)
    last=dt(item.get('last_run')); nxt=dt(next_run_for(item['id'])) if item['enabled'] else 'Desativada'
    return f'''<div class="setting-row source-row" data-source-id="{item['id']}" data-name="{name}" data-path="{path}" data-schedule="{schedule}"><div class="source-icon">▦</div><div class="source-info"><b>{name}</b><span>{path}</span><div class="source-timing"><span>Última: <strong>{esc(last)}</strong></span><span>Próxima: <strong>{esc(nxt)}</strong></span></div><em class="source-status {status.lower()}">{status_label}</em></div><small>{esc(schedule_label)}</small><button class="refresh-source" title="Forçar atualização agora">↻</button><label class="switch"><input class="source-toggle" type="checkbox" {checked}><i></i></label><button class="dots source-menu" title="Editar fonte">•••</button></div>'''

@router.get('/configuracoes',response_class=HTMLResponse)
def page():
    settings=store.get_settings(); rows=''.join(source_row(i) for i in store.list_sources())
    logs=''.join(f'<li><span>{escape(line[:19])}</span><b>{escape(line.split(" | ")[1] if " | " in line else "INFO")}</b><code>{escape(line.split(" | ",2)[-1])}</code></li>' for line in store.recent_events(30)) or '<li>Nenhum evento registrado.</li>'
    selected=lambda value,target: 'selected' if value==target else ''
    content=f'''<div id="toast" class="toast" role="status"></div><div class="page-tools"><p>Fontes, agendamentos, performance e diagnóstico do sistema.</p><button id="new-source" class="btn primary">+ Nova fonte</button></div><div class="settings-grid"><div class="panel"><div class="panel-head"><div><small>DADOS</small><h2>Fontes e atualizações</h2></div></div><div id="source-list">{rows}</div></div><div class="panel compact"><div class="panel-head"><div><small>PERFORMANCE</small><h2>Limites do motor</h2></div></div><form id="settings-form" class="form-grid"><label>Máximo de jobs simultâneos<input name="max_jobs" type="number" min="1" max="16" value="{settings['max_jobs']}" required></label><label>Linhas por página<select name="page_size"><option {selected(settings['page_size'],50)}>50</option><option {selected(settings['page_size'],100)}>100</option><option {selected(settings['page_size'],250)}>250</option><option {selected(settings['page_size'],500)}>500</option></select></label><label>Tempo de cache (segundos)<input name="cache_seconds" type="number" min="0" max="86400" value="{settings['cache_seconds']}" required></label><label>Tempo limite da consulta (segundos)<input name="query_timeout" type="number" min="5" max="600" value="{settings['query_timeout']}" required></label><button class="btn primary full form-span" type="submit">Salvar configurações</button></form></div></div><div class="panel logs-panel"><div class="panel-head"><div><small>DIAGNÓSTICO</small><h2>Logs do sistema</h2></div><div><a class="btn secondary" href="/api/logs/download">Baixar log</a><button id="refresh-logs" class="btn primary">↻ Atualizar logs</button></div></div><ul id="log-list" class="log-list">{logs}</ul></div>
    <dialog id="source-dialog"><form id="source-form"><div class="modal-head"><div><small>CONFIGURAÇÃO DA FONTE</small><h2 id="source-title">Nova fonte</h2></div><button type="button" class="modal-close">×</button></div><input name="id" type="hidden"><label>Nome da fonte<input name="name" maxlength="80" required placeholder="Ex.: Carteira"></label><label>Origem dos dados</label><div class="path-field"><input name="path" maxlength="500" required placeholder="Selecione um arquivo ou uma pasta"><button id="browse-folder" type="button">Selecionar pasta</button><button id="browse-file" type="button">Selecionar arquivo</button></div><button id="validate-path" type="button" class="btn path-check">✓ Validar acesso</button><div class="schedule-box"><label>Tipo de agendamento<select name="schedule_type"><option value="manual">Somente manual</option><option value="interval">Por intervalo</option><option value="daily">Diariamente</option><option value="weekly">Dias da semana</option></select></label><div id="interval-fields" class="schedule-fields hidden"><label>Executar a cada<input name="schedule_value" type="number" min="1" max="999" value="30"></label><label>Unidade<select name="schedule_unit"><option value="minuto(s)">Minuto(s)</option><option value="hora(s)">Hora(s)</option></select></label></div><div id="time-fields" class="schedule-fields hidden"><label>Horário<input name="schedule_time" type="time" value="06:00"></label></div><div id="week-fields" class="week-fields hidden"><label><input type="checkbox" name="week_day" value="seg">Seg</label><label><input type="checkbox" name="week_day" value="ter">Ter</label><label><input type="checkbox" name="week_day" value="qua">Qua</label><label><input type="checkbox" name="week_day" value="qui">Qui</label><label><input type="checkbox" name="week_day" value="sex">Sex</label><label><input type="checkbox" name="week_day" value="sab">Sáb</label><label><input type="checkbox" name="week_day" value="dom">Dom</label></div></div><label class="check-line"><input name="enabled" type="checkbox" checked> Fonte e agendamento ativos</label><div class="modal-actions"><button id="delete-source" type="button" class="btn danger hidden">Excluir</button><span></span><button type="button" class="btn secondary modal-close">Cancelar</button><button type="submit" class="btn primary">Salvar fonte</button></div></form></dialog>'''
    return layout('Configurações','/configuracoes',content)

@router.post('/api/configuracoes/settings')
def save_settings(payload: SettingsPayload):
    return {'ok':True,'data':store.save_settings(payload.model_dump()),'message':'Configurações salvas.'}

@router.get('/api/configuracoes/picker-token')
def picker_token():
    key=os.getenv('SYNC_API_KEY','').strip()
    if len(key)<24:raise HTTPException(503,'A chave do sincronizador não está configurada no Railway.')
    token=hashlib.sha256((key+'|operacional-local-picker').encode()).hexdigest()
    return {'ok':True,'token':token,'url':'http://127.0.0.1:8765'}

@router.post('/api/configuracoes/sources')
def add_source(payload: SourcePayload):
    try: source_id=store.create_source(payload.model_dump())
    except sqlite3.IntegrityError:
        store.logger.warning('VALIDATION_ERROR | Fonte duplicada | name=%s',payload.name)
        raise HTTPException(409,'Já existe uma fonte com esse nome.')
    refresh_jobs(); return {'ok':True,'id':source_id,'message':'Fonte criada com sucesso.'}

@router.put('/api/configuracoes/sources/{source_id}')
def edit_source(source_id:int,payload:SourcePayload):
    try: store.update_source(source_id,payload.model_dump())
    except KeyError: raise HTTPException(404,'Fonte não encontrada.')
    except sqlite3.IntegrityError: raise HTTPException(409,'Já existe uma fonte com esse nome.')
    refresh_jobs(); return {'ok':True,'message':'Fonte atualizada.'}

@router.patch('/api/configuracoes/sources/{source_id}/toggle')
def toggle_source(source_id:int,payload:TogglePayload):
    try: store.toggle_source(source_id,payload.enabled)
    except KeyError: raise HTTPException(404,'Fonte não encontrada.')
    refresh_jobs(); return {'ok':True,'message':'Agendamento atualizado.'}

@router.delete('/api/configuracoes/sources/{source_id}')
def remove_source(source_id:int):
    try: store.delete_source(source_id)
    except KeyError: raise HTTPException(404,'Fonte não encontrada.')
    refresh_jobs(); return {'ok':True,'message':'Fonte excluída.'}

@router.get('/api/logs')
def logs(): return {'ok':True,'lines':store.recent_events(120)}

@router.post('/api/configuracoes/validate-path')
def validate_path(payload:PathPayload):
    if __import__('os').name!='nt':
        return {'ok':True,'exists':None,'is_directory':None,'message':'Caminho registrado. O sincronizador local fará a validação no computador.'}
    path=Path(payload.path).expanduser(); exists=path.exists(); is_dir=path.is_dir() if exists else False
    store.logger.info('PATH_VALIDATION | path=%s | exists=%s | is_dir=%s',payload.path,exists,is_dir)
    return {'ok':True,'exists':exists,'is_directory':is_dir,'message':'Pasta encontrada e acessível.' if is_dir else 'Caminho não encontrado ou sem acesso.'}

@router.post('/api/configuracoes/select-path')
def select_path(payload:PickerPayload):
    try:
        selected=open_native_dialog(payload.mode)
        if selected: store.logger.info('PATH_SELECTED | mode=%s | path=%s',payload.mode,selected)
        else: store.logger.info('PATH_SELECTION_CANCELLED | mode=%s',payload.mode)
        return {'ok':True,'selected':selected or None}
    except NativeDialogError as exc:
        store.logger.error('PATH_DIALOG_UNAVAILABLE | mode=%s | erro=%s',payload.mode,exc)
        raise HTTPException(503,str(exc))
    except Exception as exc:
        store.logger.exception('PATH_DIALOG_FAILED | mode=%s | erro=%s',payload.mode,exc)
        raise HTTPException(500,'O Windows não conseguiu abrir o seletor. Digite ou cole o caminho e consulte os logs.')

@router.post('/api/configuracoes/sources/{source_id}/run')
def run_source(source_id:int,background_tasks:BackgroundTasks):
    if not store.get_source(source_id): raise HTTPException(404,'Fonte não encontrada.')
    if __import__('os').name!='nt':
        store.request_source_sync(source_id)
        return {'ok':True,'message':'Atualização solicitada ao sincronizador local.'}
    store.set_source_status(source_id,'RUNNING','Atualização solicitada · aguardando processamento')
    background_tasks.add_task(job_manager.run_source,source_id)
    return {'ok':True,'message':'Atualização iniciada em segundo plano.'}

@router.get('/api/configuracoes/sources/{source_id}/status')
def source_status(source_id:int):
    result=job_manager.status(source_id)
    if not result: raise HTTPException(404,'Fonte não encontrada.')
    return {'ok':True,'data':result}

@router.get('/api/logs/download',response_class=PlainTextResponse)
def download_logs():
    return PlainTextResponse('\n'.join(reversed(store.recent_logs(500))),headers={'Content-Disposition':'attachment; filename="operacional.log"'})
