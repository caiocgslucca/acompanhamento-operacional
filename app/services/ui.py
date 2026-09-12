from html import escape

ICON=lambda body:f'<svg viewBox="0 0 24 24" aria-hidden="true">{body}</svg>'
NAV = [
    ("/", ICON('<path d="M3 11 12 4l9 7v9H6v-9"/><path d="M9 20v-6h6v6"/>'), "Visão Geral"),
    ("/carteira", ICON('<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>'), "Carteira"),
    ("/reab", ICON('<path d="M4 8h16v12H4z"/><path d="M7 4h10v4M8 12h8M8 16h5"/>'), "Reab"),
    ("/producao", ICON('<path d="M4 20V9M10 20V4M16 20v-7M22 20H2"/>'), "Demanda e Produção"),
    ("/recebimento", ICON('<path d="M12 3v13M7 11l5 5 5-5M4 20h16"/>'), "Recebimento"),
    ("/expedicao", ICON('<path d="M12 21V8M7 13l5-5 5 5M4 4h16"/>'), "Expedição"),
    ("/inventario", ICON('<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M7 11h2M11 11h2M15 11h2M7 15h2M11 15h2M15 15h2"/>'), "Inventário"),
    ("/reversa", ICON('<path d="M4 10a8 8 0 1 0 3-5M4 4v6h6"/>'), "Reversa"),
    ("/cargas", ICON('<path d="M3 7h13v10H3zM16 10h3l2 3v4h-5z"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>'), "Cargas e Capas"),
    ("/saude", ICON('<path d="M12 21s8-4 8-11V5l-8-3-8 3v5c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-5"/>'), "Saúde"),
    ("/configuracoes", ICON('<circle cx="12" cy="12" r="3"/><path d="M19 13.5v-3l-2-.7-.7-1.7.9-1.9-2.1-2.1-1.9.9-1.7-.7L10.5 2h-3l-.7 2-1.7.7-1.9-.9-2.1 2.1.9 1.9-.7 1.7-2 .7v3l2 .7.7 1.7-.9 1.9 2.1 2.1 1.9-.9 1.7.7.7 2h3l.7-2 1.7-.7 1.9.9 2.1-2.1-.9-1.9.7-1.7 2-.7Z"/>'), "Configurações"),
]

def layout(title: str, active: str, content: str, eyebrow: str = "OPERAÇÃO EM TEMPO REAL") -> str:
    nav = "".join(f'<a class="nav-item {"active" if p == active else ""}" href="{p}"><span>{i}</span>{n}</a>' for p,i,n in NAV)
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · Leo Madeiras</title><link rel="icon" href="/static/app-icon.svg"><link rel="stylesheet" href="/static/style.css?v=33"><link rel="stylesheet" href="/static/config.css?v=33"><link rel="stylesheet" href="/static/carteira.css?v=33"><script src="/static/app.js?v=33" defer></script></head>
    <body><aside><div class="brand"><div class="brand-symbol"><svg viewBox="0 0 56 56" aria-label="Leo Madeiras"><defs><linearGradient id="brandGold" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#FFD04A"/><stop offset="1" stop-color="#E9A817"/></linearGradient></defs><rect x="1" y="1" width="54" height="54" rx="15" fill="url(#brandGold)"/><path d="M17 13v29h25" fill="none" stroke="#06442E" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><path d="M27 13v18h15" fill="none" stroke="#08783F" stroke-width="3" stroke-linecap="round" opacity=".72"/><path d="M12 48c10-4 23-4 34 0" fill="none" stroke="#FFF2B9" stroke-width="1.5" opacity=".75"/></svg></div><div class="brand-copy"><b>LEO</b><small>MADEIRAS</small><em>Operação inteligente</em></div><button id="sidebar-toggle" title="Recolher menu" aria-label="Recolher menu">‹</button></div><nav>{nav}</nav><div class="sidebar-foot"><i></i><span>Sistema operacional<br><b>Online e atualizado</b></span></div></aside>
    <main><header><div><small>{eyebrow}</small><h1>{escape(title)}</h1></div><div class="header-actions"><button class="icon-btn">⌕</button><button class="icon-btn">♧<b class="dot"></b></button><div class="avatar">CC</div><div class="user"><b>Caio Cezar</b><small>Administrador · <a href="/logout">Sair</a></small></div></div></header><section class="content">{content}</section></main><dialog id="confirm-dialog" class="confirm-dialog"><div class="confirm-icon">!</div><div><small>CONFIRMAÇÃO NECESSÁRIA</small><h2 id="confirm-title">Confirmar ação</h2><p id="confirm-message"></p></div><div class="confirm-actions"><button id="confirm-cancel" class="btn secondary">Cancelar</button><button id="confirm-accept" class="btn danger">Confirmar</button></div></dialog></body></html>'''

def kpi(label, value, delta, icon, tone="green"):
    cls = "up" if str(delta).startswith("+") else "neutral"
    return f'<article class="kpi"><div class="kpi-top"><span>{label}</span><i class="kpi-icon {tone}">{icon}</i></div><strong>{value}</strong><div class="trend {cls}">{delta}</div></article>'

def table(headers, rows):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>"+"".join(f"<td>{c}</td>" for c in row)+"</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'

def module_page(title, active, description, metrics, headers, rows, accent="green"):
    cards = "".join(kpi(*m) for m in metrics)
    content = f'<div class="page-tools"><p>{description}</p><div><button class="btn secondary">Exportar</button><button class="btn primary">↻ Atualizar dados</button></div></div><div class="kpi-grid">{cards}</div><div class="panel"><div class="panel-head"><div><small>DETALHAMENTO</small><h2>{title} por operação</h2></div><div class="filters"><button>Todos os status⌄</button><button>Hoje⌄</button></div></div>{table(headers, rows)}<div class="pagination"><span>Mostrando 1–5 de 318.424 registros</span><div><button>‹</button><button class="selected">1</button><button>2</button><button>3</button><button>›</button></div></div></div>'
    return layout(title, active, content)
