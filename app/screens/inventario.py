from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.services.ui import module_page
router=APIRouter()
@router.get('/inventario',response_class=HTMLResponse)
def page(): return module_page('Inventário','/inventario','Controle contagens de piso, facial, endereços e divergências.',[("Contagens abertas","14","-3 esta semana","▦","green"),("Endereços","1.826","82% concluído","⌖","blue"),("Divergências","47","2,6%","!","amber"),("Acuracidade","98,7%","+0,4 p.p.","✓","green")],["Contagem","Área","Responsável","Endereços","Divergência","Status"],[["INV-1048","Picking A","Carlos Lima","240","4","<span class='pill blue'>Em contagem</span>"],["INV-1047","Piso 01","Ana Souza","318","2","<span class='pill green'>Concluído</span>"],["INV-1046","Facial B","João Alves","196","8","<span class='pill amber'>Recontagem</span>"],["INV-1045","Pulmão 03","Marcos Reis","422","1","<span class='pill green'>Concluído</span>"],["INV-1044","Picking C","Lia Gomes","284","12","<span class='pill red'>Divergência</span>"]])
