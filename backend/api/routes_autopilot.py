import asyncio
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import HTMLResponse,FileResponse
from pydantic import BaseModel
from backend.accounts.context import current_account,owner_id_for_session
from backend.models.db import SessionLocal
from backend.autopilot.store import Store
from backend.autopilot.service import collect,tick

async def owner_only(request:Request):
    if request.method not in ("GET","HEAD","OPTIONS") and request.headers.get("X-JN-Autopilot-Intent")!="owner-action":
        raise HTTPException(403,"Explicit dashboard action required")
    with SessionLocal() as db:
        if current_account.get()!=owner_id_for_session(db):raise HTTPException(403,'Owner account required')

router=APIRouter(prefix='/autopilot',tags=['autopilot'],dependencies=[Depends(owner_only)])
class Mode(BaseModel):enabled:bool
class Employer(BaseModel):company:str;url_prefix:str

@router.get('/page',response_class=HTMLResponse)
def page():return HTMLResponse((Path(__file__).resolve().parents[1]/'autopilot/dashboard.html').read_text(),headers={'Content-Security-Policy':"frame-ancestors 'self'",'X-Frame-Options':'SAMEORIGIN'})

@router.get('')
def status():
    store=Store();cfg=store.config()
    return {'config':{k:v for k,v in cfg.items() if k!='cv_path'},'cv_configured':bool(cfg['cv_path']), 'queue':store.rows()}

@router.post('/discover')
def discover():return {'added':collect()}

@router.post('/mode')
async def mode(body:Mode):
    Store().save_config({'enabled':body.enabled})
    if body.enabled:asyncio.get_running_loop().create_task(tick())
    return {'enabled':body.enabled}

@router.post('/run')
async def run():
    asyncio.create_task(tick());return {'started':True}

@router.post('/{ident}/authorize')
async def authorize(ident:str):
    try:Store().authorize(ident)
    except ValueError as exc:raise HTTPException(409,str(exc))
    asyncio.create_task(tick());return {'authorized':True}

@router.post('/{ident}/resume')
async def resume(ident:str):
    try:Store().resume(ident)
    except ValueError as exc:raise HTTPException(409,str(exc))
    asyncio.create_task(tick());return {'queued':True}

@router.post('/employers')
async def employer(body:Employer):
    # The owner must explicitly enter the employer and its official application path.
    u=urlsplit(body.url_prefix)
    if not body.company.strip() or u.scheme!='https' or not u.hostname or u.path in ('','/'):
        raise HTTPException(422,'Provide the employer name and a specific HTTPS application path, not a whole shared ATS host')
    if u.query or u.fragment or u.username or u.password:raise HTTPException(422,'Use a clean application path')
    store=Store();cfg=store.config();rows=cfg['employers']
    grant={'company':body.company.strip(),'url_prefix':body.url_prefix.rstrip('/')}
    if grant not in rows:rows.append(grant)
    store.save_config({'employers':rows})
    collect();asyncio.create_task(tick())
    return {'saved':True}

@router.delete('/employers')
def clear_employers():
    store=Store();store.save_config({'employers':[]});store.revoke_standing();return {'cleared':True}

@router.get('/{ident}/proof')
def proof(ident:str):
    store=Store();row=store.row(ident)
    if not row or not row['evidence']:raise HTTPException(404,'No proof yet')
    path=Path(row['evidence']).resolve()
    if path.parent!=store.root or not path.is_file():raise HTTPException(404,'Proof unavailable')
    return FileResponse(path,media_type='image/png')
