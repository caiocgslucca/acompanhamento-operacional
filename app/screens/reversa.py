from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.services.ui import module_page
router=APIRouter()
@router.get('/reversa',response_class=HTMLResponse)
def page(): return module_page('Logística Reversa','/reversa','Rastreie entrada, nota fiscal, motorista e destino da devolução.',[("Entradas hoje","186","+14,2%","↺","green"),("Em análise","32","7 prioritárias","◷","amber"),("Finalizadas","142","94,1%","✓","blue"),("Sem documento","12","-4 vs. ontem","!","amber")],["Protocolo","Nota fiscal","Motorista","Motivo","Volumes","Status"],[["REV-61842","NF-771928","Paulo Mendes","Avaria","18","<span class='pill blue'>Em análise</span>"],["REV-61838","NF-771902","Luiz Rocha","Recusa","7","<span class='pill green'>Finalizado</span>"],["REV-61831","NF-771856","Rafael Dias","Sobra","12","<span class='pill amber'>Aguardando</span>"],["REV-61828","Sem NF","Diego Martins","Devolução","5","<span class='pill red'>Pendência</span>"],["REV-61819","NF-771721","André Silva","Avaria","9","<span class='pill green'>Finalizado</span>"]])
