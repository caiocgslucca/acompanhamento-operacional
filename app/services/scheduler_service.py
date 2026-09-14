import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from app.services import config_store as store
from app.services.job_manager import run_source

scheduler=BackgroundScheduler(daemon=True)
DAY_MAP={'seg':'mon','ter':'tue','qua':'wed','qui':'thu','sex':'fri','sab':'sat','dom':'sun'}

def trigger_for(raw):
    try: cfg=json.loads(raw)
    except Exception: return None
    kind=cfg.get('type')
    if kind=='interval':
        value=max(1,int(cfg.get('value',1))); return IntervalTrigger(**({'minutes':value} if cfg.get('unit','').startswith('minuto') else {'hours':value}))
    hour,minute=map(int,cfg.get('time','06:00').split(':'))
    if kind=='daily': return CronTrigger(hour=hour,minute=minute)
    if kind=='weekly':
        days=','.join(DAY_MAP[d] for d in cfg.get('days','').split(',') if d in DAY_MAP)
        return CronTrigger(day_of_week=days,hour=hour,minute=minute) if days else None
    return None

def refresh_jobs():
    if os.name!='nt':
        if scheduler.running:scheduler.remove_all_jobs()
        store.logger.info('SCHEDULER_REMOTE_MODE | agendamentos controlados pelo sincronizador local')
        return 0
    if not scheduler.running: scheduler.start()
    scheduler.remove_all_jobs()
    count=0
    for source in store.list_sources():
        if not source['enabled']: continue
        trigger=trigger_for(source['schedule'])
        if trigger:
            scheduler.add_job(run_source,trigger,args=[source['id']],id=f"source_{source['id']}",max_instances=1,coalesce=True,misfire_grace_time=300,replace_existing=True)
            count+=1
    store.logger.info('SCHEDULER_REFRESHED | jobs_ativos=%s',count)
    return count

def reset_source_job(source_id):
    """Recalcula somente a próxima execução da fonte que acabou de atualizar."""
    if os.name!='nt':return next_run_for(source_id)
    if not scheduler.running:scheduler.start()
    job_id=f"source_{source_id}"
    if scheduler.get_job(job_id):scheduler.remove_job(job_id)
    source=store.get_source(source_id)
    if not source or not source['enabled']:return None
    trigger=trigger_for(source['schedule'])
    if not trigger:return None
    scheduler.add_job(run_source,trigger,args=[source_id],id=job_id,max_instances=1,coalesce=True,misfire_grace_time=300,replace_existing=True)
    job=scheduler.get_job(job_id)
    store.logger.info('SOURCE_NEXT_RUN_RECALCULATED | id=%s | next=%s',source_id,job.next_run_time.isoformat() if job and job.next_run_time else None)
    return job.next_run_time.isoformat() if job and job.next_run_time else None

def next_run_for(source_id):
    source=store.get_source(source_id)
    if not source or not source.get('enabled') or not source.get('last_run'):return None
    try:cfg=json.loads(source.get('schedule') or '{}')
    except (TypeError,json.JSONDecodeError):return None
    try:
        last=datetime.fromisoformat(source['last_run'])
        if last.tzinfo is None:last=last.replace(tzinfo=timezone.utc)
    except (TypeError,ValueError):return None
    kind=cfg.get('type');local_zone=ZoneInfo('America/Sao_Paulo');local_last=last.astimezone(local_zone)
    if kind=='interval':
        value=max(1,int(cfg.get('value',1)));delta=timedelta(minutes=value) if str(cfg.get('unit','')).startswith('minuto') else timedelta(hours=value)
        candidate=last+delta
        now=datetime.now(timezone.utc)
        # Nunca devolve horário vencido na interface. Se um ciclo atrasou, avança
        # para a próxima janela futura mantendo a cadência configurada.
        while candidate<=now:
            candidate+=delta
        return candidate.isoformat(timespec='seconds')
    if kind not in ('daily','weekly'):return None
    try:hour,minute=map(int,str(cfg.get('time','06:00')).split(':'))
    except ValueError:hour,minute=6,0
    candidate=local_last.replace(hour=hour,minute=minute,second=0,microsecond=0)
    if candidate<=local_last:candidate+=timedelta(days=1)
    if kind=='weekly':
        day_map={'seg':0,'ter':1,'qua':2,'qui':3,'sex':4,'sab':5,'dom':6};allowed={day_map[d] for d in str(cfg.get('days','')).split(',') if d in day_map}
        if not allowed:return None
        while candidate.weekday() not in allowed:candidate+=timedelta(days=1)
    return candidate.astimezone(timezone.utc).isoformat(timespec='seconds')
