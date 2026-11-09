import asyncio
import json
import os
from pathlib import Path
import time
from .store import Store,scope_matches
from .engine import Engine

_gate=asyncio.Lock()
_engine=None

def collect():
    from backend.models.db import SessionLocal,Job,Application
    from backend.accounts.context import use_account,owner_id_for_session
    from backend.scraper._shared.link_kinds import job_link,_on_board
    store=Store();cfg=store.config();added=0
    with SessionLocal() as db:
        with use_account(owner_id_for_session(db)):
            jobs=db.query(Job).filter(Job.status.in_(['new','saved']),Job.best_cv_score>=cfg['min_score']).all()
            for j in jobs:
                if j.loc_country not in ('DE','IE','SE') or j.open_state=='closed':continue
                if db.query(Application).filter(Application.job_id==j.id).first():continue
                url=job_link(j)
                if not url or _on_board(url):continue
                before=store.row(str(j.id))
                store.put({'job_id':str(j.id),'company':j.company or '', 'title':j.title or '', 'url':url})
                if store.row(str(j.id)) is None:continue
                if not before:added+=1
                elif before['state']!='awaiting_authorization':continue
                # A standing permission must name both the employer and its verified ATS path.
                for a in cfg['employers']:
                    if a.get('company')==j.company and scope_matches(url,a.get('url_prefix','')):
                        store.authorize(str(j.id),source='standing');break
    return added

def payload(ident):
    from backend.models.db import SessionLocal,Job,Application
    from backend.accounts.context import use_account,owner_id_for_session
    from backend.accounts.owned import get_persona
    with SessionLocal() as db:
        with use_account(owner_id_for_session(db)):
            job=db.query(Job).filter(Job.id==ident).first()
            if not job or job.status=='applied' or job.open_state=='closed' or db.query(Application).filter(Application.job_id==ident).first():
                return None
            p=get_persona(db)
            return {'contact':p.contact or {},'work_auth':p.work_auth or {},'preferences':p.preferences or {},'compensation':p.compensation or {},
                    'resume_content':p.resume_content or {},'qa_bank':p.qa_bank or []}

def record_received(ident,evidence):
    from backend.models.db import SessionLocal,Job,Application,utcnow
    from backend.accounts.context import use_account,owner_id_for_session
    with SessionLocal() as db:
        with use_account(owner_id_for_session(db)):
            job=db.query(Job).filter(Job.id==ident).first()
            if not job:return
            if not db.query(Application).filter(Application.job_id==ident).first():
                db.add(Application(job_id=job.id,status='applied',notes='Autopilot: employer receipt verified. Local proof: '+evidence,
                    status_transitions=[{'from':None,'to':'applied','at':utcnow().isoformat(),'source':'autopilot_verified'}]))
            job.status='applied';db.commit()

async def tick():
    global _engine
    if _gate.locked():return
    async with _gate:
        store=Store()
        if not store.config()['enabled']:return
        # One host-native worker across processes, not just across event-loop tasks.
        import fcntl
        lock=(store.root/'worker.lock').open('a')
        try:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return
            if _engine is None:store.recover();_engine=Engine(store)
            collect()
            for _ in range(store.config()['max_per_six_hours']):
                if not store.config()['enabled'] or store.remaining()==0:break
                if sum(not p.is_closed() for p in _engine.pages.values())>=10:break
                row=store.claim()
                if not row:break
                profile=payload(row['job_id'])
                if profile is None:
                    store.transition(row['job_id'],'needs_attention','Already applied or no longer available; no repeat application')
                    continue
                state=await _engine.run(row,profile)
                if state=='submitted':
                    verified=store.row(row['job_id'])
                    record_received(row['job_id'],verified['evidence'])
        finally:
            fcntl.flock(lock,fcntl.LOCK_UN);lock.close()

async def shutdown():
    global _engine
    if _engine is not None:
        try:
            if _engine.context:await _engine.context.close()
        finally:
            if _engine.playwright:await _engine.playwright.stop()
            _engine=None
