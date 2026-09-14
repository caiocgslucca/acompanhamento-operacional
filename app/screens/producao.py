from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Query,BackgroundTasks
from fastapi.responses import HTMLResponse,StreamingResponse
from app.services.ui import layout
from app.services.producao_engine import build
from app.services.carteira_engine import carteira_related_names,clean_name
from app.services import config_store as store
from app.services.job_manager import run_source,data_revision
from app.services.scheduler_service import next_run_for

router=APIRouter()
def _filter(key,label):return f'''<div class="multi-filter" data-filter="{key}"><button type="button" class="multi-trigger"><span><small>{label}</small><b>Todos</b></span><i>⌄</i></button><div class="multi-menu"><div class="multi-options"></div><button type="button" class="multi-apply">Aplicar seleção</button></div></div>'''

@router.get('/producao',response_class=HTMLResponse)
def page():
    filters=''.join(_filter(key,label) for key,label in (('empresa','Filial'),('classe','Classe'),('data','Data oficial'),('turno','Turno'),('turno_rota','Turno Rota')))
    content=f'''<div id="toast" class="toast" role="status"></div><div class="carteira-head"><div><p>Visão consolidada da demanda, separação e saldo de produção por onda.</p><div id="production-meta" class="data-meta">Preparando indicadores…</div><div class="update-timeline"><span id="production-status" class="status-badge idle">Aguardando dados</span><span id="production-updated">Última atualização: —</span><span id="production-next">Próxima atualização dos dados: —</span><span id="production-pdf-next">Próxima geração do PDF: —</span></div></div><div class="carteira-actions"><button type="button" class="btn secondary report-settings" data-report-module="producao">⚙ Configurar PDF</button><a id="export-production" class="btn secondary" href="/api/producao/pdf">▧ Gerar relatório PDF</a><button id="refresh-production" class="btn primary">↻ Atualizar produção</button></div></div><div id="production-filters" class="filter-panel production-filters">{filters}<button id="clear-production-filters" class="clear-filter">Limpar filtros</button></div><div id="production-error" class="data-error hidden"></div><div id="production-loading" class="matrix-loading"><i></i><b>Calculando demanda e produção…</b><span>As ondas permanecem fixas durante a atualização.</span></div><section id="production-content" class="production-panel hidden"><div class="production-title"><div><small>DEMANDA E EXECUÇÃO POR ONDA</small><h2>Controle de Demanda e Produção</h2></div><span id="production-progress">0% concluído</span></div><div id="production-table" class="production-scroll"></div></section>'''
    return layout('Controle de Demanda e Produção','/producao',content)

@router.get('/api/producao/data')
def data(empresa:list[str]=Query([]),classe:list[str]=Query([]),data:list[str]=Query([]),turno:list[str]=Query([]),turno_rota:list[str]=Query([])):
    try:
        result=build({'empresa':empresa,'classe':classe,'data':data,'turno':turno,'turno_rota':turno_rota});sources=[s for s in store.list_sources() if clean_name(s['name']) in carteira_related_names()];source=next((s for s in sources if clean_name(s['name'])=='CARTEIRA'),None)
        latest=max((s.get('last_run') for s in sources if s.get('last_run')),default=result['meta'].get('updated_at'));result['meta']['updated_at']=latest
        result['meta']['next_run']=next_run_for(source['id']) if source else None;result['meta']['revision']=data_revision();return {'ok':True,'data':result}
    except Exception as exc:store.logger.exception('PRODUCAO_BUILD_FAILED | erro=%s',exc);return {'ok':False,'message':str(exc)}

@router.get('/api/producao/status')
def status():
    sources=[s for s in store.list_sources() if clean_name(s['name']) in carteira_related_names()]
    return {'ok':True,'revision':data_revision(),'data':[{'id':s['id'],'name':s['name'],'status':s.get('status'),'last_run':s.get('last_run'),'next_run':next_run_for(s['id'])} for s in sources]}

@router.post('/api/producao/refresh')
def refresh(background_tasks:BackgroundTasks):
    sources=[s for s in store.list_sources() if clean_name(s['name']) in carteira_related_names()]
    if not {'CARTEIRA','ONDA'}.issubset({clean_name(s['name']) for s in sources}):return {'ok':False,'message':'Cadastre as fontes Carteira e Onda.'}
    if __import__('os').name!='nt':
        for source in sources:store.request_source_sync(source['id'])
        return {'ok':True,'message':'Atualização solicitada ao sincronizador local.'}
    for source in sources:store.set_source_status(source['id'],'RUNNING','Atualização solicitada · aguardando processamento');background_tasks.add_task(run_source,source['id'])
    return {'ok':True,'message':'Atualização da demanda e produção iniciada.'}

@router.get('/api/producao/pdf')
def pdf(empresa:list[str]=Query([]),classe:list[str]=Query([]),data:list[str]=Query([]),turno:list[str]=Query([]),turno_rota:list[str]=Query([])):
    from reportlab.lib.pagesizes import A2,landscape
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Table,TableStyle
    selected={'empresa':empresa,'classe':classe,'data':data,'turno':turno,'turno_rota':turno_rota};result=build(selected);buffer=BytesIO();page=landscape(A2);c=canvas.Canvas(buffer,pagesize=page,pageCompression=1);width,height=page
    green=colors.HexColor('#075638');amber=colors.HexColor('#F0B323');muted=colors.HexColor('#60736A');fmt=lambda v:f'{v:,.0f}'.replace(',','.')
    c.setFillColor(green);c.rect(0,height-72,width,72,fill=1,stroke=0);c.setFillColor(amber);c.roundRect(28,height-58,38,38,8,fill=1,stroke=0);c.setFillColor(green);c.setFont('Helvetica-Bold',25);c.drawCentredString(47,height-50,'L')
    c.setFillColor(colors.white);c.setFont('Helvetica-Bold',18);c.drawString(82,height-37,'Controle de Demanda e Produção');c.setFont('Helvetica',7);c.drawString(82,height-52,'VISÃO EXECUTIVA · EXECUÇÃO POR ONDA');c.drawRightString(width-28,height-39,datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('Emitido em %d/%m/%Y às %H:%M'))
    totals=result['totals'];cards=[('REGISTROS',fmt(result['meta']['rows'])),('TOTAL A PRODUZIR',fmt(totals['produzir'])),('QTD. PENDENTE',fmt(totals['pendente'])),('% CONCLUÍDO',f"{totals['concluido']:.1f}%".replace('.',','))];card_y=height-118;card_w=(width-70)/4
    for index,(label,value) in enumerate(cards):
        x=28+index*(card_w+5);c.setFillColor(colors.HexColor('#F3F8F5'));c.roundRect(x,card_y,card_w,35,6,fill=1,stroke=0);c.setFillColor(muted);c.setFont('Helvetica-Bold',5.8);c.drawString(x+10,card_y+23,label);c.setFillColor(green);c.setFont('Helvetica-Bold',12);c.drawString(x+10,card_y+8,value)
    filter_text=[]
    for label,key in (('Filial','empresa'),('Classe','classe'),('Data oficial','data'),('Turno','turno'),('Turno Rota','turno_rota')):filter_text.append(f"{label}: {', '.join(selected[key]) if selected[key] else 'Todos'}")
    c.setFillColor(muted);c.setFont('Helvetica',6);c.drawString(28,card_y-13,'  •  '.join(filter_text))
    rows=[['CÓDIGO E DESCRIÇÃO DA ONDA','TOTAL A PRODUZIR','QTD. CANCELADA','QTD. SEPARADA','QTD. PENDENTE','% CONCLUÍDO']]
    rows += [[r['label'],fmt(r['produzir']),fmt(r['cancelado']),fmt(r['separado']),fmt(r['pendente']),f"{r['concluido']:.1f}%".replace('.',',')] for r in result['rows']]
    rows.append(['TOTAL',fmt(totals['produzir']),fmt(totals['cancelado']),fmt(totals['separado']),fmt(totals['pendente']),f"{totals['concluido']:.1f}%".replace('.',',')])
    top=card_y-48;max_height=top-36;row_height=max(13,min(21,max_height/max(1,len(rows))));table=Table(rows,colWidths=[300,118,108,108,108,92],rowHeights=[row_height]*len(rows))
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),green),('TEXTCOLOR',(0,0),(-1,0),colors.white),('BACKGROUND',(0,1),(0,-2),colors.HexColor('#E7F2EC')),('BACKGROUND',(0,-1),(-1,-1),green),('TEXTCOLOR',(0,-1),(-1,-1),colors.white),('ROWBACKGROUNDS',(1,1),(-1,-2),[colors.white,colors.HexColor('#F7F9F8')]),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),('FONTNAME',(0,1),(0,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),7),('ALIGN',(1,0),(-1,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#DCE5E0')),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]))
    _,table_height=table.wrap(width-56,max_height);table.drawOn(c,28,top-table_height);c.setStrokeColor(colors.HexColor('#DDE6E1'));c.line(28,25,width-28,25);c.setFillColor(muted);c.setFont('Helvetica',6);c.drawString(28,14,'Leo Madeiras · Acompanhamento Operacional');c.drawRightString(width-28,14,'Relatório consolidado em página única');c.showPage();c.save();buffer.seek(0);store.logger.info('PRODUCAO_PDF_EXPORTED | linhas=%s | paginas=1',result['meta']['rows'])
    return StreamingResponse(buffer,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="demanda_producao_{datetime.now(ZoneInfo('America/Sao_Paulo')):%Y%m%d_%H%M}.pdf"'})
