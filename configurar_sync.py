import getpass
import json
from pathlib import Path

root=Path(__file__).resolve().parent;target=root/'sync_config.json'
print('\nCONFIGURAÇÃO DO SINCRONIZADOR LOCAL — LEO MADEIRAS\n')
url=input('Endereço HTTPS do Railway: ').strip().rstrip('/')
key=getpass.getpass('SYNC_API_KEY configurada no Railway: ').strip()
interval=input('Verificar alterações a cada quantos minutos? [5]: ').strip() or '5'
if not url.startswith('https://'):raise SystemExit('ERRO: informe o endereço completo iniciado por https://')
if len(key)<24:raise SystemExit('ERRO: a chave precisa ter pelo menos 24 caracteres.')
try:interval=max(1,int(interval))
except ValueError:raise SystemExit('ERRO: intervalo inválido.')
payload={'server_url':url,'api_key':key,'interval_minutes':interval,'sources':{}}
target.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print('\nConfiguração salva. As fontes serão lidas automaticamente de data\\operacional.db.')
