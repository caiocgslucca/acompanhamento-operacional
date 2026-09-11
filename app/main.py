from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse, Response, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import sys
import os
import base64
import secrets
import hashlib
import hmac
import time
from urllib.parse import quote
from app.screens import home, carteira, reab, producao, recebimento, expedicao, inventario, reversa, cargas, saude, configuracoes, sync

app = FastAPI(title="Acompanhamento Operacional", version="1.0.0")
RESOURCE_ROOT=Path(getattr(sys,"_MEIPASS",Path.cwd()))
STATIC_DIR=RESOURCE_ROOT/"app"/"static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

SESSION_COOKIE='operacional_session';SESSION_SECONDS=12*60*60
def _credentials():return os.getenv('APP_USERNAME','').strip(),os.getenv('APP_PASSWORD','')
def _session_signature(expires):
    username,password=_credentials();key=hashlib.sha256(f'{username}\0{password}\0operacional'.encode()).digest()
    return hmac.new(key,str(expires).encode(),hashlib.sha256).hexdigest()
def _valid_session(request):
    try:
        expires_text,signature=request.cookies.get(SESSION_COOKIE,'').split('.',1);expires=int(expires_text)
        return expires>int(time.time()) and secrets.compare_digest(signature,_session_signature(expires))
    except (ValueError,TypeError):return False
def _safe_next(value):return value if value.startswith('/') and not value.startswith('//') else '/'
def _login_html(next_path='/',error=''):
    warning=f'<div class="login-error">{error}</div>' if error else ''
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Acesso · Acompanhamento Operacional</title><link rel="icon" href="/static/app-icon.svg"><link rel="stylesheet" href="/static/login.css"></head><body class="login-page"><main class="login-shell"><section class="login-brand"><div class="login-logo"><svg viewBox="0 0 56 56"><rect x="1" y="1" width="54" height="54" rx="15"/><path d="M17 13v29h25"/><path d="M27 13v18h15"/></svg></div><span>LEO MADEIRAS</span><h1>Operação conectada,<br>decisões mais rápidas.</h1><p>Acesse indicadores e atualizações da operação em um ambiente protegido.</p><small>ACOMPANHAMENTO OPERACIONAL</small></section><section class="login-card"><div><small>ACESSO SEGURO</small><h2>Bem-vindo</h2><p>Informe suas credenciais para continuar.</p></div>{warning}<form method="post" action="/login"><input type="hidden" name="next_path" value="{next_path}"><label>Usuário<input name="username" autocomplete="username" required autofocus placeholder="Digite seu usuário"></label><label>Senha<input type="password" name="password" autocomplete="current-password" required placeholder="Digite sua senha"></label><button type="submit">Entrar no sistema <span>→</span></button></form><footer><i></i>Conexão protegida e acesso restrito</footer></section></main></body></html>'''

@app.get('/login',response_class=HTMLResponse)
def login_page(request:Request,next:str='/'):
    if _valid_session(request):return RedirectResponse(_safe_next(next),303)
    return HTMLResponse(_login_html(_safe_next(next)))
@app.post('/login')
def login(request:Request,username:str=Form(...),password:str=Form(...),next_path:str=Form('/')):
    expected_user,expected_password=_credentials()
    if not expected_user or not expected_password:return HTMLResponse(_login_html('/','O acesso protegido não foi configurado.'),503)
    if not (secrets.compare_digest(username,expected_user) and secrets.compare_digest(password,expected_password)):
        return HTMLResponse(_login_html(_safe_next(next_path),'Usuário ou senha incorretos.'),401)
    expires=int(time.time())+SESSION_SECONDS;response=RedirectResponse(_safe_next(next_path),303)
    response.set_cookie(SESSION_COOKIE,f'{expires}.{_session_signature(expires)}',max_age=SESSION_SECONDS,httponly=True,samesite='lax',secure=request.headers.get('x-forwarded-proto')=='https')
    return response
@app.get('/logout')
def logout():
    response=RedirectResponse('/login',303);response.delete_cookie(SESSION_COOKIE);return response

@app.middleware("http")
async def disable_api_cache(request: Request, call_next):
    username,password=_credentials()
    public=request.url.path in ('/api/health','/login') or request.url.path.startswith('/static/') or request.url.path.startswith('/api/sync/')
    if username and password and not public and not _valid_session(request):
        if request.url.path.startswith('/api/'):return JSONResponse(status_code=401,content={'ok':False,'message':'Sessão expirada. Entre novamente.'})
        return RedirectResponse('/login?next='+quote(request.url.path),303)
    response=await call_next(request)
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma']='no-cache'
        response.headers['Expires']='0'
    return response

for router in (home.router, carteira.router, reab.router, producao.router, recebimento.router, expedicao.router,
               inventario.router, reversa.router, cargas.router, saude.router,
               configuracoes.router, sync.router):
    app.include_router(router)

from app.services.config_store import initialize, logger
initialize()
from app.services.scheduler_service import refresh_jobs
refresh_jobs()

@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.exception("UNHANDLED_ERROR | method=%s | path=%s | error=%s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"ok": False, "message": "Erro interno registrado no log."})

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
