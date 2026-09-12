from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.services import config_store as store
from app.services.ui import layout, kpi, table

router = APIRouter()


@router.get('/saude', response_class=HTMLResponse)
def page():
    sources = store.list_sources()
    active = [source for source in sources if source.get('enabled')]
    success = [source for source in active if (source.get('status') or '').upper() == 'SUCCESS']
    running = [source for source in active if (source.get('status') or '').upper() == 'RUNNING']
    errors = [source for source in active if (source.get('status') or '').upper() == 'ERROR']
    cards = ''.join([
        kpi('Fontes ativas', str(len(active)), 'Configuração real', '▤'),
        kpi('Atualizadas', str(len(success)), 'Execução concluída', '✓'),
        kpi('Em processamento', str(len(running)), 'Estado atual', '↻', 'blue'),
        kpi('Com erro', str(len(errors)), 'Estado atual', '!', 'amber'),
    ])
    rows = [[escape(source['name']), escape(source.get('status') or 'IDLE'), escape(source.get('status_message') or '—')] for source in sources]
    details = table(['Fonte', 'Estado real', 'Última mensagem'], rows) if rows else '<p class="empty-state">Nenhuma fonte cadastrada.</p>'
    return layout('Saúde do Sistema', '/saude', f'<div class="page-tools"><p>Diagnóstico baseado nos estados reais informados pelo sincronizador.</p></div><div class="kpi-grid">{cards}</div><div class="panel"><div class="panel-head"><div><small>FONTES</small><h2>Estado atual</h2></div></div>{details}</div>')
