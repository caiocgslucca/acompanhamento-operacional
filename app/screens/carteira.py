from io import BytesIO
from datetime import datetime
from fastapi import APIRouter, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from app.services.ui import layout
from app.services.carteira_engine import build, clean_name, carteira_related_names
from app.services import config_store as store
from app.services.job_manager import run_source, data_revision
from app.services.scheduler_service import next_run_for

router=APIRouter()
FILTER_LABELS=(('empresa','Filial'),('rota','Rota'),('status','Status da separação'))

@router.get('/carteira',response_class=HTMLResponse)
def page():
    filters=''.join(f'''<div class="multi-filter" data-filter="{key}"><button type="button" class="multi-trigger"><span><small>{label}</small><b>Todos</b></span><i>⌄</i></button><div class="multi-menu"><div class="multi-options"></div><button type="button" class="multi-apply">Aplicar seleção</button></div></div>''' for key,label in FILTER_LABELS)
    content=f'''<div id="toast" class="toast" role="status"></div><div class="carteira-head"><div><p>Visão consolidada de todas as filiais e arquivos publicados.</p><div id="carteira-meta" class="data-meta">Preparando visão consolidada…</div><div class="update-timeline"><span id="carteira-status" class="status-badge idle">Aguardando dados</span><span id="carteira-updated">Última atualização: —</span><span id="carteira-next">Próxima atualização: —</span></div></div><div class="carteira-actions"><a id="export-carteira" class="btn secondary" href="/api/carteira/pdf">▧ Gerar relatório PDF</a><button id="refresh-carteira" class="btn primary">↻ Atualizar Carteira</button></div></div><div id="carteira-filters" class="filter-panel">{filters}<button id="clear-carteira-filters" class="clear-filter">Limpar filtros</button></div><div id="carteira-error" class="data-error hidden"></div><div id="carteira-loading" class="matrix-loading"><i></i><b>Consolidando arquivos e calculando matrizes…</b><span>A interface permanece disponível durante o processamento.</span></div><div id="carteira-content" class="matrix-grid hidden"><section class="matrix-panel"><div class="matrix-title"><div><small>CARTEIRA POR FAIXA · CLASSE FIXA ZCHP</small><h2>DS × Onda</h2></div><strong id="aging-total">0</strong></div><div id="matrix-aging" class="matrix-scroll"></div></section><section class="matrix-panel"><div class="matrix-title"><div><small>CARTEIRA POR CLASSE</small><h2>Classe × Onda</h2></div><strong id="class-total">0</strong></div><div id="matrix-class" class="matrix-scroll"></div></section></div>'''
    return layout('Acompanhamento Carteira Geral','/carteira',content)

def filters_dict(empresa,rota,status):return {'empresa':empresa,'classe':[],'rota':rota,'status':status}

@router.get('/api/carteira/data')
def data(empresa:list[str]=Query([]),rota:list[str]=Query([]),status:list[str]=Query([])):
    try:
        result=build(filters_dict(empresa,rota,status)); source=next((s for s in store.list_sources() if clean_name(s['name'])=='CARTEIRA'),None)
        result['meta']['next_run']=next_run_for(source['id']) if source else None
        related=[s.get('last_run') for s in store.list_sources() if clean_name(s['name']) in carteira_related_names() and s.get('last_run')]
        result['meta']['data_version']=max(related) if related else result['meta'].get('updated_at')
        result['meta']['revision']=data_revision()
        return {'ok':True,'data':result}
    except Exception as exc:
        store.logger.exception('CARTEIRA_BUILD_FAILED | erro=%s',exc); return {'ok':False,'message':str(exc)}

@router.get('/api/carteira/status')
def carteira_status():
    sources=[s for s in store.list_sources() if clean_name(s['name']) in carteira_related_names()]
    return {'ok':True,'revision':data_revision(),'data':[{'id':s['id'],'name':s['name'],'status':s.get('status'),'status_message':s.get('status_message'),'last_run':s.get('last_run'),'next_run':next_run_for(s['id'])} for s in sources]}

@router.post('/api/carteira/refresh')
def refresh(background_tasks:BackgroundTasks):
    sources=[s for s in store.list_sources() if clean_name(s['name']) in carteira_related_names()]
    if not {'CARTEIRA','ONDA'}.issubset({clean_name(s['name']) for s in sources}):return {'ok':False,'message':'Cadastre e ative as fontes “Carteira” e “Onda” em Configurações.'}
    if __import__('os').name!='nt':
        for source in sources:store.request_source_sync(source['id'])
        return {'ok':True,'message':'Atualização solicitada ao sincronizador local.'}
    for source in sources:
        store.set_source_status(source['id'],'RUNNING','Atualização solicitada · aguardando processamento')
        background_tasks.add_task(run_source,source['id'])
    return {'ok':True,'message':'Atualização da Carteira e complementos iniciada.'}

def _one_page_table(matrix,width,max_height):
    from reportlab.platypus import Table,TableStyle
    from reportlab.lib import colors
    columns=matrix['columns']; fmt=lambda value:f"{value:,.0f}".replace(',','.') if value else ''
    short=lambda value:(str(value)[:31]+'…') if len(str(value))>32 else str(value)
    rows=[[matrix.get('row_header','DS_ONDA'),*columns,'TOTAL']]
    rows += [[short(row['label']),*(fmt(row['values'][c]) for c in columns),fmt(row['total'])] for row in matrix['rows']]
    rows.append(['TOTAL',*(fmt(matrix['totals'][c]) for c in columns),fmt(matrix['grand_total'])])
    row_height=max(13,min(18,max_height/max(1,len(rows)))); label_width=160; total_width=52
    value_width=max(20,(width-label_width-total_width)/max(1,len(columns)))
    table=Table(rows,colWidths=[label_width]+[value_width]*len(columns)+[total_width],rowHeights=[row_height]*len(rows))
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#075638')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('BACKGROUND',(0,1),(0,-2),colors.HexColor('#E7F2EC')),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#075638')),('TEXTCOLOR',(0,-1),(-1,-1),colors.white),('BACKGROUND',(-1,1),(-1,-2),colors.HexColor('#E4F4EB')),('TEXTCOLOR',(-1,1),(-1,-2),colors.HexColor('#075638')),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),('FONTNAME',(0,1),(0,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),4.8),('ALIGN',(1,0),(-1,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#DCE5E0')),('ROWBACKGROUNDS',(1,1),(-2,-2),[colors.white,colors.HexColor('#F7F9F8')]),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))
    table.setStyle(TableStyle([('FONTSIZE',(0,0),(-1,-1),6.8)]))
    return table

@router.get('/api/carteira/pdf')
def pdf(empresa:list[str]=Query([]),rota:list[str]=Query([]),status:list[str]=Query([])):
    from reportlab.lib.pagesizes import A2,landscape
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    result=build(filters_dict(empresa,rota,status)); buffer=BytesIO(); page=landscape(A2); pdf_canvas=canvas.Canvas(buffer,pagesize=page,pageCompression=1); width,height=page
    green=colors.HexColor('#075638'); amber=colors.HexColor('#F0B323'); muted=colors.HexColor('#60736A'); fmt=lambda v:f'{v:,.0f}'.replace(',','.')
    pdf_canvas.setFillColor(green);pdf_canvas.rect(0,height-72,width,72,fill=1,stroke=0);pdf_canvas.setFillColor(amber);pdf_canvas.roundRect(28,height-58,38,38,8,fill=1,stroke=0);pdf_canvas.setFillColor(green);pdf_canvas.setFont('Helvetica-Bold',25);pdf_canvas.drawCentredString(47,height-50,'L')
    pdf_canvas.setFillColor(colors.white);pdf_canvas.setFont('Helvetica-Bold',18);pdf_canvas.drawString(82,height-37,'Acompanhamento Carteira Geral');pdf_canvas.setFont('Helvetica',7);pdf_canvas.drawString(82,height-52,'VISÃO EXECUTIVA · OPERAÇÃO LOGÍSTICA');pdf_canvas.drawRightString(width-28,height-39,datetime.now().strftime('Emitido em %d/%m/%Y às %H:%M'))
    cards=[('REGISTROS',fmt(result['meta']['rows'])),('PENDENTE',fmt(result['meta']['total_pending'])),('DS × ONDA · ZCHP',fmt(result['matrix_aging']['grand_total'])),('CLASSE × ONDA',fmt(result['matrix_class']['grand_total']))]
    card_y=height-118;card_w=(width-70)/4
    for index,(label,value) in enumerate(cards):
        x=28+index*(card_w+5);pdf_canvas.setFillColor(colors.HexColor('#F3F8F5'));pdf_canvas.roundRect(x,card_y,card_w,35,6,fill=1,stroke=0);pdf_canvas.setFillColor(muted);pdf_canvas.setFont('Helvetica-Bold',5.8);pdf_canvas.drawString(x+10,card_y+23,label);pdf_canvas.setFillColor(green);pdf_canvas.setFont('Helvetica-Bold',12);pdf_canvas.drawString(x+10,card_y+8,value)
    selected=[]
    for label,values in [('Filial',empresa),('Rota',rota),('Status',status)]:selected.append(f"{label}: {', '.join(values) if values else 'Todos'}")
    pdf_canvas.setFillColor(muted);pdf_canvas.setFont('Helvetica',6);pdf_canvas.drawString(28,card_y-13,'  •  '.join(selected))
    margin=28;gap=16;panel_width=(width-(margin*2)-gap)/2;title_y=card_y-39;table_top=title_y-14;table_bottom=34;max_height=table_top-table_bottom
    for x,title,matrix in ((margin,'CARTEIRA POR FAIXA · DS × ONDA · CLASSE FIXA ZCHP',result['matrix_aging']),(margin+panel_width+gap,'CARTEIRA POR CLASSE · CLASSE × ONDA',result['matrix_class'])):
        pdf_canvas.setFillColor(green);pdf_canvas.setFont('Helvetica-Bold',8);pdf_canvas.drawString(x,title_y,title);table=_one_page_table(matrix,panel_width,max_height);_,table_height=table.wrap(panel_width,max_height);table.drawOn(pdf_canvas,x,table_top-table_height)
    pdf_canvas.setStrokeColor(colors.HexColor('#DDE6E1'));pdf_canvas.line(28,25,width-28,25);pdf_canvas.setFillColor(muted);pdf_canvas.setFont('Helvetica',6);pdf_canvas.drawString(28,14,'Leo Madeiras · Acompanhamento Operacional');pdf_canvas.drawRightString(width-28,14,'Relatório consolidado em página única');pdf_canvas.showPage();pdf_canvas.save();buffer.seek(0);store.logger.info('CARTEIRA_PDF_EXPORTED | linhas=%s | paginas=1',result['meta']['rows'])
    return StreamingResponse(buffer,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="carteira_{datetime.now():%Y%m%d_%H%M}.pdf"'})
