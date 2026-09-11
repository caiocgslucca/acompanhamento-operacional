from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.services.ui import module_page
router=APIRouter()
@router.get('/recebimento',response_class=HTMLResponse)
def page(): return module_page('Recebimento','/recebimento','Controle agendas, notas fiscais, docas e armazenagem.',[("Agendas hoje","92","+6 vs. ontem","⇩","green"),("Em doca","14","2 críticas","▰","amber"),("Concluídas","68","93,2%","✓","blue"),("Ruptura","3","-2 vs. ontem","!","amber")],["Agenda","Fornecedor","Nota fiscal","Doca","Previsto","Status"],[["AG-38241","Berneck","460223","D04","08:30","<span class='pill green'>Concluído</span>"],["AG-38246","Duratex","883192","D02","09:10","<span class='pill blue'>Em descarga</span>"],["AG-38249","Arauco","774218","D07","10:00","<span class='pill amber'>Aguardando</span>"],["AG-38252","Eucatex","192746","D01","11:20","<span class='pill red'>Divergência</span>"],["AG-38258","Sonae","663901","D05","13:00","<span class='pill amber'>Aguardando</span>"]])
