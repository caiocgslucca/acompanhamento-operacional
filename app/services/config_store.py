import json
import logging
import os
import sqlite3
import re
import sys
import uuid
from pathlib import Path
from threading import Lock

ROOT = Path(os.getenv("OPERACIONAL_ROOT","")).expanduser().resolve() if os.getenv("OPERACIONAL_ROOT") else (Path(sys.executable).resolve().parent if getattr(sys,"frozen",False) else Path(__file__).resolve().parents[2])
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "operacional.db"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / "operacional.log"
_lock = Lock()

logger = logging.getLogger("operacional")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%d/%m/%Y %H:%M:%S")
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

DEFAULT_SETTINGS = {"max_jobs": 2, "page_size": 100, "cache_seconds": 300, "query_timeout": 30}
DEFAULT_SOURCES = [
    ("Carteira", r"C:\Bases\Carteira", "A cada 30 minutos", 1),
    ("Recebimento", r"C:\Bases\Recebimento", "A cada 1 hora", 1),
    ("Expedição", r"C:\Bases\Expedicao", "A cada 30 minutos", 0),
    ("Inventário", r"C:\Bases\Inventario", "Diariamente às 06:00", 0),
]

def connect():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    return con

def initialize():
    with _lock, connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, path TEXT NOT NULL, schedule TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS picker_requests (id TEXT PRIMARY KEY, mode TEXT NOT NULL, status TEXT NOT NULL, selected_path TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        """)
        columns={row[1] for row in con.execute("PRAGMA table_info(sources)")}
        for name,sql_type,default in (("status","TEXT","'IDLE'"),("status_message","TEXT","''"),("last_run","TEXT","NULL"),("origin_path","TEXT","''"),("sync_revision","INTEGER","0")):
            if name not in columns: con.execute(f"ALTER TABLE sources ADD COLUMN {name} {sql_type} DEFAULT {default}")
        con.execute("UPDATE sources SET origin_path=path WHERE COALESCE(origin_path,'')='' AND path NOT LIKE '%cloud_sources%'")
        # Versões anteriores gravavam o horário UTC sem o identificador de fuso.
        # Acrescentar +00:00 permite que navegador e relatórios convertam corretamente.
        legacy_times=con.execute("SELECT id,last_run FROM sources WHERE last_run IS NOT NULL AND last_run<>''").fetchall()
        for row in legacy_times:
            try:
                from datetime import datetime, timezone
                parsed=datetime.fromisoformat(row['last_run'])
                if parsed.tzinfo is None:
                    con.execute("UPDATE sources SET last_run=? WHERE id=?",(parsed.replace(tzinfo=timezone.utc).isoformat(timespec='seconds'),row['id']))
            except (TypeError,ValueError):pass
        con.execute("INSERT OR IGNORE INTO settings(id,payload) VALUES(1,?)", (json.dumps(DEFAULT_SETTINGS),))
        if con.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0:
            con.executemany("INSERT INTO sources(name,path,schedule,enabled) VALUES(?,?,?,?)", DEFAULT_SOURCES)
        server_sources=(
            ('Carteira',os.getenv('CARTEIRA_SOURCE_PATH'),os.getenv('CARTEIRA_SCHEDULE','{"type":"interval","value":5,"unit":"minuto(s)"}')),
            ('Onda',os.getenv('ONDA_SOURCE_PATH'),os.getenv('ONDA_SCHEDULE','{"type":"interval","value":5,"unit":"minuto(s)"}')),
        )
        for name,path,schedule in server_sources:
            if not path:continue
            current=con.execute("SELECT id FROM sources WHERE UPPER(name)=UPPER(?)",(name,)).fetchone()
            if current:
                con.execute("UPDATE sources SET path=?,schedule=?,enabled=1 WHERE id=?",(path,schedule,current['id']))
            else:
                con.execute("INSERT INTO sources(name,path,schedule,enabled) VALUES(?,?,?,1)",(name,path,schedule))
        con.execute("UPDATE sources SET origin_path=path WHERE COALESCE(origin_path,'')='' AND path NOT LIKE '%cloud_sources%'")
    logger.info("STARTUP | Banco de configurações inicializado | db=%s", DB_PATH)

def list_sources():
    with connect() as con: return [dict(row) for row in con.execute("SELECT * FROM sources ORDER BY id")]

def get_source(source_id):
    with connect() as con:
        row=con.execute("SELECT * FROM sources WHERE id=?",(source_id,)).fetchone()
        return dict(row) if row else None

def set_source_status(source_id,status,message):
    from datetime import datetime, timezone
    with _lock, connect() as con:
        con.execute("UPDATE sources SET status=?,status_message=?,last_run=? WHERE id=?",(status,message,datetime.now(timezone.utc).isoformat(timespec='seconds'),source_id))

def get_settings():
    with connect() as con: return json.loads(con.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])

def save_settings(payload):
    data = {k: int(payload[k]) for k in DEFAULT_SETTINGS}
    with _lock, connect() as con: con.execute("UPDATE settings SET payload=? WHERE id=1", (json.dumps(data),))
    logger.info("SETTINGS_SAVED | %s", data)
    return data

def create_source(data):
    with _lock, connect() as con:
        cur=con.execute("INSERT INTO sources(name,path,origin_path,schedule,enabled,sync_revision,status,status_message) VALUES(?,?,?,?,?,1,'IDLE','Aguardando sincronizador local')",(data["name"].strip(),data["path"].strip(),data["path"].strip(),data["schedule"].strip(),int(data.get("enabled",True))))
        source_id=cur.lastrowid
    logger.info("SOURCE_CREATED | id=%s | name=%s | path=%s",source_id,data["name"],data["path"])
    return source_id

def update_source(source_id,data):
    with _lock, connect() as con:
        current=con.execute("SELECT path FROM sources WHERE id=?",(source_id,)).fetchone()
        if not current: raise KeyError(source_id)
        runtime_path=current['path'] if 'cloud_sources' in str(current['path']) else data['path'].strip()
        cur=con.execute("UPDATE sources SET name=?,path=?,origin_path=?,schedule=?,enabled=?,sync_revision=COALESCE(sync_revision,0)+1,status='IDLE',status_message='Aguardando sincronizador local' WHERE id=?",(data["name"].strip(),runtime_path,data["path"].strip(),data["schedule"].strip(),int(data.get("enabled",True)),source_id))
        if not cur.rowcount: raise KeyError(source_id)
    logger.info("SOURCE_UPDATED | id=%s | name=%s",source_id,data["name"])

def upsert_synced_source(name,path):
    """Publica uma versão recebida do agente local sem depender de caminhos do Windows."""
    with _lock, connect() as con:
        row=con.execute("SELECT id FROM sources WHERE UPPER(name)=UPPER(?)",(name,)).fetchone()
        schedule='{"type":"manual"}'
        if row:
            source_id=row['id'];con.execute("UPDATE sources SET path=?,enabled=1 WHERE id=?",(str(path),source_id))
        else:
            source_id=con.execute("INSERT INTO sources(name,path,origin_path,schedule,enabled,sync_revision) VALUES(?,?,?, ?,1,0)",(name,str(path),'',schedule)).lastrowid
    logger.info("SYNC_SOURCE_PUBLISHED | id=%s | fonte=%s | caminho=%s",source_id,name,path)
    return source_id

def publish_synced_source(source_id,path):
    """Publica os arquivos recebidos mantendo a identidade e o agendamento da fonte."""
    with _lock, connect() as con:
        row=con.execute("SELECT id,name FROM sources WHERE id=?",(source_id,)).fetchone()
        if not row:raise KeyError(source_id)
        con.execute("UPDATE sources SET path=? WHERE id=?",(str(path),source_id))
    logger.info("SYNC_SOURCE_PUBLISHED | id=%s | fonte=%s | caminho=%s",source_id,row['name'],path)
    return source_id

def restore_source_runtime(source_id,path):
    with _lock, connect() as con: con.execute("UPDATE sources SET path=? WHERE id=?",(str(path),source_id))

def toggle_source(source_id,enabled):
    with _lock, connect() as con:
        cur=con.execute("UPDATE sources SET enabled=? WHERE id=?",(int(enabled),source_id))
        if not cur.rowcount: raise KeyError(source_id)
    logger.info("SOURCE_TOGGLED | id=%s | enabled=%s",source_id,enabled)

def request_source_sync(source_id):
    with _lock, connect() as con:
        cur=con.execute("UPDATE sources SET sync_revision=COALESCE(sync_revision,0)+1,status='RUNNING',status_message='Solicitação enviada ao sincronizador local' WHERE id=?",(source_id,))
        if not cur.rowcount: raise KeyError(source_id)
    logger.info("SOURCE_SYNC_REQUESTED | id=%s",source_id)

def delete_source(source_id):
    with _lock, connect() as con:
        row=con.execute("SELECT name FROM sources WHERE id=?",(source_id,)).fetchone()
        if not row: raise KeyError(source_id)
        con.execute("DELETE FROM sources WHERE id=?",(source_id,))
    logger.warning("SOURCE_DELETED | id=%s | name=%s",source_id,row["name"])

def recent_logs(limit=120):
    if not LOG_PATH.exists(): return []
    return LOG_PATH.read_text("utf-8",errors="replace").splitlines()[-max(1,min(limit,500)):][::-1]

def recent_events(limit=120):
    """Eventos legíveis para a interface; stack traces permanecem no download técnico."""
    lines=recent_logs(500)
    events=[line for line in lines if re.match(r'^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2} \| (INFO|WARNING|ERROR|CRITICAL) \| ',line)]
    return events[:max(1,min(limit,200))]

def create_picker_request(mode):
    from datetime import datetime, timedelta
    request_id=uuid.uuid4().hex;now=datetime.now().isoformat(timespec='seconds')
    cutoff=(datetime.now()-timedelta(minutes=10)).isoformat(timespec='seconds')
    with _lock, connect() as con:
        con.execute("DELETE FROM picker_requests WHERE created_at<?",(cutoff,))
        con.execute("UPDATE picker_requests SET status='CANCELLED',error='Substituído por uma nova solicitação',updated_at=? WHERE status IN ('PENDING','PROCESSING')",(now,))
        con.execute("INSERT INTO picker_requests(id,mode,status,created_at,updated_at) VALUES(?,?,'PENDING',?,?)",(request_id,mode,now,now))
    logger.info('PICKER_REQUESTED | id=%s | mode=%s',request_id,mode)
    return request_id

def claim_picker_request():
    from datetime import datetime
    now=datetime.now().isoformat(timespec='seconds')
    with _lock, connect() as con:
        row=con.execute("SELECT * FROM picker_requests WHERE status='PENDING' ORDER BY created_at LIMIT 1").fetchone()
        if not row:return None
        con.execute("UPDATE picker_requests SET status='PROCESSING',updated_at=? WHERE id=? AND status='PENDING'",(now,row['id']))
        return dict(row)

def complete_picker_request(request_id,selected_path='',error=''):
    from datetime import datetime
    status='ERROR' if error else ('COMPLETED' if selected_path else 'CANCELLED')
    with _lock, connect() as con:
        cur=con.execute("UPDATE picker_requests SET status=?,selected_path=?,error=?,updated_at=? WHERE id=?",(status,selected_path,error,datetime.now().isoformat(timespec='seconds'),request_id))
        if not cur.rowcount:raise KeyError(request_id)
    logger.info('PICKER_FINISHED | id=%s | status=%s',request_id,status)

def get_picker_request(request_id):
    with connect() as con:
        row=con.execute("SELECT * FROM picker_requests WHERE id=?",(request_id,)).fetchone()
        return dict(row) if row else None
