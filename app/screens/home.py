from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.services.ui import layout, kpi

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def page():
    cards = "".join([
        kpi("Pedidos em carteira", "18.642", "+8,4% vs. ontem", "▤"),
        kpi("Quantidade pendente", "284.519", "-3,1% vs. ontem", "◷", "amber"),
        kpi("Expedidos hoje", "4.286", "+12,7% vs. ontem", "⇧"),
        kpi("Nível de serviço", "96,8%", "+1,2 p.p.", "✓", "blue"),
    ])
    modules = [("Carteira","18.642 pedidos","/carteira","▤"),("Reab","DS e classes por loja","/reab","▣"),("Demanda e Produção","Execução por onda","/producao","◫"),("Recebimento","92 agendas hoje","/recebimento","⇩"),("Expedição","4.286 expedidos","/expedicao","⇧"),("Inventário","14 contagens abertas","/inventario","▦"),("Reversa","186 entradas","/reversa","↺"),("Cargas e Capas","38 em trânsito","/cargas","▰")]
    mod_html = "".join(f'<a class="module-card" href="{p}"><div class="module-icon">{i}</div><div><b>{n}</b><span>{s}</span></div><em>→</em></a>' for n,s,p,i in modules)
    bars = "".join(f'<div class="bar-row"><span>{filial}</span><div><i style="width:{pct}%"></i></div><b>{val}</b></div>' for filial,pct,val in [("1500",92,"92%"),("1002",84,"84%"),("1004",76,"76%"),("1005",66,"66%"),("1012",58,"58%")])
    content = f'<div class="welcome"><div><p>Terça-feira, 01 de setembro</p><h2>Boa tarde, Caio.</h2><span>A operação está estável. Existem <b>3 pontos de atenção</b> que precisam de acompanhamento.</span></div><button class="btn primary">↻ Atualizar operação</button></div><div class="kpi-grid">{cards}</div><div class="dashboard-grid"><div class="panel"><div class="panel-head"><div><small>ACESSO RÁPIDO</small><h2>Áreas operacionais</h2></div></div><div class="module-grid">{mod_html}</div></div><div class="panel"><div class="panel-head"><div><small>DESEMPENHO</small><h2>Nível de serviço por filial</h2></div><button class="link">Ver relatório →</button></div><div class="bars">{bars}</div></div></div><div class="status-strip"><div><i></i><span><b>Última atualização concluída</b><small>318.424 registros publicados em 2,8 segundos</small></span></div><time>Hoje, 16:30</time></div>'
    return layout("Central Operacional", "/", content)
