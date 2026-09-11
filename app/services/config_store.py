import json
import logging
import os
import sqlite3
import re
import sys
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
        """)
        columns={row[1] for row in con.execute("PRAGMA table_info(sources)")}
        for name,sql_type,default in (("status","TEXT","'IDLE'"),("status_message","TEXT","''"),("last_run","TEXT","NULL")):
            if name not in columns: con.execute(f"ALTER TABLE sources ADD COLUMN {name} {sql_type} DEFAULT {default}")
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
    logger.info("STARTUP | Banco de configurações inicializado | db=%s", DB_PATH)

def list_sources():
    with connect() as con: return [dict(row) for row in con.execute("SELECT * FROM sources ORDER BY id")]

def get_source(source_id):
    with connect() as con:
        row=con.execute("SELECT * FROM sources WHERE id=?",(source_id,)).fetchone()
        return dict(row) if row else None

def set_source_status(source_id,status,message):
    from datetime import datetime
    with _lock, connect() as con:
        con.execute("UPDATE sources SET status=?,status_message=?,last_run=? WHERE id=?",(status,message,datetime.now().isoformat(timespec='seconds'),source_id))

def get_settings():
    with connect() as con: return json.loads(con.execute("SELECT payload FROM settings WHERE id=1").fetchone()[0])

def save_settings(payload):
    data = {k: int(payload[k]) for k in DEFAULT_SETTINGS}
    with _lock, connect() as con: con.execute("UPDATE settings SET payload=? WHERE id=1", (json.dumps(data),))
    logger.info("SETTINGS_SAVED | %s", data)
    return data

def create_source(data):
    with _lock, connect() as con:
        cur=con.execute("INSERT INTO sources(name,path,schedule,enabled) VALUES(?,?,?,?)",(data["name"].strip(),data["path"].strip(),data["schedule"].strip(),int(data.get("enabled",True))))
        source_id=cur.lastrowid
    logger.info("SOURCE_CREATED | id=%s | name=%s | path=%s",source_id,data["name"],data["path"])
    return source_id

def update_source(source_id,data):
    with _lock, connect() as con:
        cur=con.execute("UPDATE sources SET name=?,path=?,schedule=?,enabled=? WHERE id=?",(data["name"].strip(),data["path"].strip(),data["schedule"].strip(),int(data.get("enabled",True)),source_id))
        if not cur.rowcount: raise KeyError(source_id)
    logger.info("SOURCE_UPDATED | id=%s | name=%s",source_id,data["name"])

def upsert_synced_source(name,path):
    """Publica uma versão recebida do agente local sem depender de caminhos do Windows."""
    with _lock, connect() as con:
        row=con.execute("SELECT id FROM sources WHERE UPPER(name)=UPPER(?)",(name,)).fetchone()
        schedule='{"type":"manual"}'
        if row:
            source_id=row['id'];con.execute("UPDATE sources SET path=?,schedule=?,enabled=1 WHERE id=?",(str(path),schedule,source_id))
        else:
            source_id=con.execute("INSERT INTO sources(name,path,schedule,enabled) VALUES(?,?,?,1)",(name,str(path),schedule)).lastrowid
    logger.info("SYNC_SOURCE_PUBLISHED | id=%s | fonte=%s | caminho=%s",source_id,name,path)
    return source_id

def toggle_source(source_id,enabled):
    with _lock, connect() as con:
        cur=con.execute("UPDATE sources SET enabled=? WHERE id=?",(int(enabled),source_id))
        if not cur.rowcount: raise KeyError(source_id)
    logger.info("SOURCE_TOGGLED | id=%s | enabled=%s",source_id,enabled)

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
