from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.services.ui import module_page
router=APIRouter()
@router.get('/expedicao',response_class=HTMLResponse)
def page(): return module_page('Expedição','/expedicao','Visão de ondas, separação, conferência e carregamento.',[("Ondas abertas","24","-4 vs. ontem","≋","green"),("Separado","42.860","+12,7%","▦","blue"),("Em conferência","1.284","8 cargas","◷","amber"),("Expedido","4.286","96,5%","✓","green")],["Onda","Carga","Rota","Volumes","Doca","Status"],[["ON-28412","CG-7284","SP-042","428","D12","<span class='pill blue'>Conferência</span>"],["ON-28408","CG-7279","SP-018","392","D09","<span class='pill green'>Expedido</span>"],["ON-28401","CG-7272","RJ-011","311","D03","<span class='pill amber'>Separação</span>"],["ON-28398","CG-7268","MG-006","286","D10","<span class='pill red'>Atrasado</span>"],["ON-28394","CG-7264","SP-067","241","D08","<span class='pill green'>Expedido</span>"]])
