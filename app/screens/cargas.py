from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.services.ui import module_page
router=APIRouter()
@router.get('/cargas',response_class=HTMLResponse)
def page(): return module_page('Cargas e Capas','/cargas','Prestação de contas de capas, MDF, paletes e equipamentos.',[("Em trânsito","38","6 retornam hoje","▰","green"),("Capas fora","124","-8 vs. ontem","▱","blue"),("Paletes fora","286","+12 vs. ontem","▦","amber"),("Pendências","9","3 críticas","!","amber")],["Carga","Motorista","Transportadora","Capas","Paletes","Status"],[["CG-7284","Paulo Mendes","TransLeo","12","24","<span class='pill blue'>Em trânsito</span>"],["CG-7279","Luiz Rocha","Rodomax","8","18","<span class='pill green'>Prestado</span>"],["CG-7272","Rafael Dias","TransLeo","14","32","<span class='pill amber'>Aguardando retorno</span>"],["CG-7268","Diego Martins","Expresso SP","6","12","<span class='pill red'>Atrasado</span>"],["CG-7264","André Silva","Rodomax","10","20","<span class='pill green'>Prestado</span>"]])
