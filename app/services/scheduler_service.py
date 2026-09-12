import json
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
    job=scheduler.get_job(f"source_{source_id}") if scheduler.running else None
    return job.next_run_time.isoformat() if job and job.next_run_time else None
