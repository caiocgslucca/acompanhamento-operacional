from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.services.ui import layout, kpi, table
router=APIRouter()
@router.get('/saude',response_class=HTMLResponse)
def page():
    cards=''.join([kpi('Saúde geral','Excelente','Todos serviços online','✓'),kpi('API média','84 ms','-18 ms esta semana','↯','blue'),kpi('Última carga','2,8 s','318.424 registros','⇄','green'),kpi('Base analítica','284 MB','Parquet + DuckDB','▦','amber')])
    rows=[["Carteira","318.424","2,8 s","84 ms","<span class='pill green'>Saudável</span>"],["Recebimento","92.186","1,4 s","61 ms","<span class='pill green'>Saudável</span>"],["Expedição","184.622","2,1 s","72 ms","<span class='pill green'>Saudável</span>"],["Inventário","46.830","0,9 s","48 ms","<span class='pill green'>Saudável</span>"],["Reversa","28.414","1,1 s","56 ms","<span class='pill amber'>Atenção</span>"]]
    return layout('Saúde do Sistema','/saude',f'<div class="page-tools"><p>Performance, disponibilidade e integridade das fontes.</p><button class="btn primary">Executar diagnóstico</button></div><div class="kpi-grid">{cards}</div><div class="panel"><div class="panel-head"><div><small>MONITORAMENTO</small><h2>Desempenho por módulo</h2></div><span class="live"><i></i> Ao vivo</span></div>{table(["Módulo","Registros","Atualização","Consulta média","Estado"],rows)}</div>')
