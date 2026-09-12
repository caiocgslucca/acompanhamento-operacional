from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.services import config_store as store
from app.services.scheduler_service import next_run_for
from app.services.ui import layout, kpi, table

router = APIRouter()
BRAZIL = ZoneInfo("America/Sao_Paulo")


def _time(value):
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
        return parsed.astimezone(BRAZIL).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return escape(str(value))


def _status(source):
    status = (source.get("status") or "IDLE").upper()
    labels = {"SUCCESS": "Atualizada", "RUNNING": "Atualizando", "ERROR": "Erro", "IDLE": "Aguardando"}
    tones = {"SUCCESS": "green", "RUNNING": "blue", "ERROR": "red", "IDLE": "amber"}
    return f'<span class="pill {tones.get(status, "amber")}">{labels.get(status, escape(status))}</span>'


@router.get("/", response_class=HTMLResponse)
def page():
    sources = store.list_sources()
    enabled = [source for source in sources if source.get("enabled")]
    success = [source for source in enabled if (source.get("status") or "").upper() == "SUCCESS"]
    running = [source for source in enabled if (source.get("status") or "").upper() == "RUNNING"]
    errors = [source for source in enabled if (source.get("status") or "").upper() == "ERROR"]
    cards = "".join([
        kpi("Fontes cadastradas", str(len(sources)), "Dados da configuração", "▤"),
        kpi("Fontes ativas", str(len(enabled)), "Sincronização habilitada", "✓"),
        kpi("Atualizadas", str(len(success)), "Última execução concluída", "↻", "blue"),
        kpi("Com erro", str(len(errors)), "Verifique os logs" if errors else "Nenhuma falha ativa", "!", "amber"),
    ])
    modules = [
        ("Carteira", "Matrizes consolidadas dos arquivos publicados", "/carteira", "▤"),
        ("Reab", "Reabastecimento por loja e faixa DS", "/reab", "▣"),
        ("Demanda e Produção", "Execução por onda com dados da Carteira", "/producao", "◫"),
    ]
    module_html = "".join(f'<a class="module-card" href="{path}"><div class="module-icon">{icon}</div><div><b>{name}</b><span>{description}</span></div><em>→</em></a>' for name, description, path, icon in modules)
    rows = [[escape(source["name"]), _status(source), _time(source.get("last_run")), _time(next_run_for(source["id"])) if source.get("enabled") else "Desativada", escape(source.get("status_message") or "—")] for source in sources]
    source_table = table(["Fonte", "Estado", "Última conclusão", "Próxima execução", "Detalhe"], rows) if rows else '<p class="empty-state">Nenhuma fonte cadastrada. Cadastre as pastas reais em Configurações.</p>'
    state_text = f"{len(running)} atualização(ões) em andamento" if running else "Sincronizador aguardando a próxima janela configurada"
    content = f'''<div class="welcome"><div><h2>Central Operacional</h2><span>Esta visão utiliza somente fontes cadastradas e execuções reais do sincronizador.</span></div><a class="btn primary" href="/configuracoes">Configurar fontes</a></div><div class="kpi-grid">{cards}</div><div class="panel"><div class="panel-head"><div><small>ACESSO RÁPIDO</small><h2>Módulos disponíveis</h2></div></div><div class="module-grid">{module_html}</div></div><div class="panel"><div class="panel-head"><div><small>SINCRONIZAÇÃO REAL</small><h2>Fontes e janelas de atualização</h2></div></div>{source_table}</div><div class="status-strip"><div><i></i><span><b>{state_text}</b><small>Horários calculados conforme o agendamento individual de cada fonte.</small></span></div></div>'''
    return layout("Central Operacional", "/", content)
