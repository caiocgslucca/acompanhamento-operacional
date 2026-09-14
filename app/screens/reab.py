from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from app.services.ui import layout
from app.services import config_store as store
from app.services.reab_engine import build, related_source_names
from app.services.carteira_engine import clean_name
from app.services.job_manager import run_source, data_revision
from app.services.scheduler_service import next_run_for
from app.screens.carteira import _one_page_table

router=APIRouter()
FILTER_LABELS=(('empresa','Filial'),('rota','Rota'),('status','Status da separação'))
def filters_dict(empresa,rota,status):return {'empresa':empresa,'classe':[],'rota':rota,'status':status}

@router.get('/reab',response_class=HTMLResponse)
def page():
    filters=''.join(f'''<div class="multi-filter" data-filter="{key}"><button type="button" class="multi-trigger"><span><small>{label}</small><b>Todos</b></span><i>⌄</i></button><div class="multi-menu"><div class="multi-options"></div><button type="button" class="multi-apply">Aplicar seleção</button></div></div>''' for key,label in FILTER_LABELS)
    content=f'''<div id="toast" class="toast" role="status"></div><div class="carteira-head"><div><p>Visão de reabastecimento por loja, faixa DS e classe.</p><div id="carteira-meta" class="data-meta">Preparando visão consolidada…</div><div class="update-timeline"><span id="carteira-status" class="status-badge idle">Aguardando dados</span><span id="carteira-updated">Última atualização: —</span><span id="carteira-next">Próxima atualização dos dados: —</span><span id="carteira-pdf-next">Próxima geração do PDF: —</span></div></div><div class="carteira-actions"><button type="button" class="btn secondary report-settings" data-report-module="reab">⚙ Configurar PDF</button><a id="export-carteira" class="btn secondary" href="/api/reab/pdf">▧ Gerar relatório PDF</a><button id="refresh-carteira" class="btn primary">↻ Atualizar Reab</button></div></div><div id="carteira-filters" data-api-base="/api/reab" data-page-name="Reab" class="filter-panel">{filters}<button id="clear-carteira-filters" class="clear-filter">Limpar filtros</button></div><div id="carteira-error" class="data-error hidden"></div><div id="carteira-loading" class="matrix-loading"><i></i><b>Consolidando lojas e calculando matrizes…</b><span>A interface permanece disponível durante o processamento.</span></div><div id="carteira-content" class="matrix-grid hidden"><section class="matrix-panel"><div class="matrix-title"><div><small>CLASSE VS DS VS LOJA · CLASSE FIXA ZCHP</small><h2>DS × Loja</h2></div><strong id="aging-total">0</strong></div><div id="matrix-aging" class="matrix-scroll"></div></section><section class="matrix-panel"><div class="matrix-title"><div><small>CLASSE VS LOJA</small><h2>Classes × Loja</h2></div><strong id="class-total">0</strong></div><div id="matrix-class" class="matrix-scroll"></div></section></div>'''
    return layout('Acompanhamento Reab','/reab',content)

@router.get('/api/reab/data')
def data(empresa:list[str]=Query([]),rota:list[str]=Query([]),status:list[str]=Query([])):
    try:
        result=build(filters_dict(empresa,rota,status));sources=[s for s in store.list_sources() if clean_name(s['name']) in related_source_names()]
        carteira=next((s for s in sources if clean_name(s['name'])=='CARTEIRA'),None);latest=max((s.get('last_run') for s in sources if s.get('last_run')),default=result['meta'].get('updated_at'));result['meta']['updated_at']=latest;result['meta']['next_run']=next_run_for(carteira['id']) if carteira else None
        result['meta']['revision']=data_revision();return {'ok':True,'data':result}
    except Exception as exc:store.logger.exception('REAB_BUILD_FAILED | erro=%s',exc);return {'ok':False,'message':str(exc)}

@router.get('/api/reab/status')
def status():
    sources=[s for s in store.list_sources() if clean_name(s['name']) in related_source_names()]
    return {'ok':True,'revision':data_revision(),'data':[{'id':s['id'],'name':s['name'],'status':s.get('status'),'status_message':s.get('status_message'),'last_run':s.get('last_run'),'next_run':next_run_for(s['id'])} for s in sources]}

@router.post('/api/reab/refresh')
def refresh(background_tasks:BackgroundTasks):
    sources=[s for s in store.list_sources() if clean_name(s['name']) in related_source_names()]
    if not any(clean_name(s['name'])=='CARTEIRA' for s in sources):return {'ok':False,'message':'Cadastre a fonte “Carteira” em Configurações.'}
    if __import__('os').name!='nt':
        for source in sources:store.request_source_sync(source['id'])
        return {'ok':True,'message':'Atualização solicitada ao sincronizador local.'}
    for source in sources:store.set_source_status(source['id'],'RUNNING','Atualização solicitada · aguardando processamento');background_tasks.add_task(run_source,source['id'])
    return {'ok':True,'message':'Atualização da Reab iniciada.'}

@router.get('/api/reab/pdf')
def pdf(empresa:list[str]=Query([]),rota:list[str]=Query([]),status:list[str]=Query([])):
    from reportlab.lib.pagesizes import A2,landscape
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    result=build(filters_dict(empresa,rota,status));buffer=BytesIO();page=landscape(A2);c=canvas.Canvas(buffer,pagesize=page,pageCompression=1);width,height=page
    green=colors.HexColor('#075638');amber=colors.HexColor('#F0B323');muted=colors.HexColor('#60736A');fmt=lambda v:f'{v:,.0f}'.replace(',','.')
    c.setFillColor(green);c.rect(0,height-72,width,72,fill=1,stroke=0);c.setFillColor(amber);c.roundRect(28,height-58,38,38,8,fill=1,stroke=0);c.setFillColor(green);c.setFont('Helvetica-Bold',25);c.drawCentredString(47,height-50,'L')
    c.setFillColor(colors.white);c.setFont('Helvetica-Bold',18);c.drawString(82,height-37,'Acompanhamento Reab');c.setFont('Helvetica',7);c.drawString(82,height-52,'VISÃO EXECUTIVA · REABASTECIMENTO POR LOJA');c.drawRightString(width-28,height-39,datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('Emitido em %d/%m/%Y às %H:%M'))
    cards=[('REGISTROS',fmt(result['meta']['rows'])),('PENDENTE',fmt(result['meta']['total_pending'])),('DS × LOJA · ZCHP',fmt(result['matrix_aging']['grand_total'])),('CLASSES × LOJA',fmt(result['matrix_class']['grand_total']))];card_y=height-118;card_w=(width-70)/4
    for index,(label,value) in enumerate(cards):
        x=28+index*(card_w+5);c.setFillColor(colors.HexColor('#F3F8F5'));c.roundRect(x,card_y,card_w,35,6,fill=1,stroke=0);c.setFillColor(muted);c.setFont('Helvetica-Bold',5.8);c.drawString(x+10,card_y+23,label);c.setFillColor(green);c.setFont('Helvetica-Bold',12);c.drawString(x+10,card_y+8,value)
    margin=28;gap=16;panel_width=(width-margin*2-gap)/2;title_y=card_y-31;table_top=title_y-14;max_height=table_top-34
    for x,title,matrix in ((margin,'CLASSE VS DS VS LOJA · CLASSE FIXA ZCHP',result['matrix_aging']),(margin+panel_width+gap,'TODAS AS CLASSES VS LOJA',result['matrix_class'])):
        c.setFillColor(green);c.setFont('Helvetica-Bold',8);c.drawString(x,title_y,title);table=_one_page_table(matrix,panel_width,max_height);_,h=table.wrap(panel_width,max_height);table.drawOn(c,x,table_top-h)
    c.setFillColor(muted);c.setFont('Helvetica',6);c.drawString(28,14,'Leo Madeiras · Acompanhamento Reab');c.drawRightString(width-28,14,'Relatório consolidado em página única');c.showPage();c.save();buffer.seek(0)
    return StreamingResponse(buffer,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="reab_{datetime.now(ZoneInfo('America/Sao_Paulo')):%Y%m%d_%H%M}.pdf"'})
