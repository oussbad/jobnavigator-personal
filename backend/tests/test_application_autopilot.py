import asyncio
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import pytest
from backend.autopilot.store import Store,scope_matches
from backend.autopilot.engine import Engine


def item(url='https://careers.example.test/jobs/1',ident='one'):
    return {'job_id':ident,'company':'Example Employer','title':'Software Engineer','url':url}

def test_no_authorization_no_queue_claim_and_exact_scope(tmp_path):
    s=Store(tmp_path);s.put(item())
    assert s.claim() is None
    s.authorize('one');r=s.claim()
    assert s.authorized(r)
    assert not s.authorized(dict(r,url='https://other.example/jobs/1'))
    assert scope_matches('https://a.test/jobs/1/apply','https://a.test/jobs/1')
    assert not scope_matches('https://a.test/jobs/12','https://a.test/jobs/1')
    assert not scope_matches('https://a.test.evil/jobs/1','https://a.test/jobs/1')


def test_cross_source_duplicate_url_is_not_sent_twice(tmp_path):
    s=Store(tmp_path);s.put(item());s.put(item(ident='two'))
    assert len(s.rows())==1


def test_attempt_is_durable_and_never_replayed_after_restart(tmp_path):
    s=Store(tmp_path);s.put(item());s.authorize('one');s.claim();s.mark_attempt('one')
    Store(tmp_path).recover()
    assert s.row('one')['state']=='unconfirmed'
    assert s.claim() is None
    with pytest.raises(ValueError):s.authorize('one')
    with pytest.raises(ValueError):s.resume('one')


def test_submission_budget_counts_uncertain_attempts(tmp_path):
    s=Store(tmp_path);s.save_config({'max_per_six_hours':1});s.put(item());s.authorize('one');s.mark_attempt('one')
    assert s.remaining()==0
    s.put(item(url='https://careers.example.test/jobs/2',ident='two'));s.authorize('two')
    with pytest.raises(ValueError):s.mark_attempt('two')


@pytest.fixture
def local_form():
    class Handler(BaseHTTPRequestHandler):
        sent=0;receipt=True;consent=False;body=b'';landing=False
        def log_message(self,*a):pass
        def do_GET(self):
            if self.path.endswith('/received'):
                html='<h1>Thank you for applying</h1>' if Handler.receipt else '<h1>Processing</h1>'
            elif Handler.landing and not self.path.endswith('/apply'):
                html='<h1>Software Engineer</h1><a href="/jobs/1/apply">Apply now</a>'
            else:
                consent='<label><input type="checkbox" required>I agree to the Terms</label>' if Handler.consent else ''
                html='<h1>Software Engineer</h1><form method="post" enctype="multipart/form-data"><label>Full name<input name="name" required></label><label>Resume CV<input type="file" name="resume" required></label>'+consent+'<button type="submit">Submit application</button></form>'
            self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(html.encode())
        def do_POST(self):
            Handler.sent+=1;Handler.body=self.rfile.read(int(self.headers.get('Content-Length',0)))
            self.send_response(303);self.send_header('Location','/jobs/1/received');self.end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield 'http://127.0.0.1:'+str(server.server_port)+'/jobs/1',Handler
    server.shutdown()

async def deterministic_plan(page,fields,profile):
    for f in fields:
        if f['label'].startswith('Full name') and not f['value']:
            return {'action':'fill','index':f['index'],'value':'Test Candidate','evidence':'Test Candidate'}
        if f['type']=='file' and not f['value']:return {'action':'upload','index':f['index']}
    return {'action':'submit','index':next(f['index'] for f in fields if f['tag']=='button')}

async def close(engine):
    if engine.context:await engine.context.close()
    if engine.playwright:await engine.playwright.stop()

@pytest.mark.asyncio
async def test_real_browser_fills_uploads_submits_and_verifies_local_receipt(tmp_path,local_form):
    url,handler=local_form;s=Store(tmp_path);cv=tmp_path/'cv.pdf';cv.write_bytes(b'%PDF-1.4 test fixture only')
    s.save_config({'cv_path':str(cv)});s.put(item(url));s.authorize('one');row=s.claim()
    e=Engine(s,planner=deterministic_plan,test_mode=True)
    try:
        result=await e.run(row,{'name':'Test Candidate'})
        assert result=='submitted',s.row('one')['reason']
        assert handler.sent==1
        assert b'Test Candidate' in handler.body
        assert b'%PDF-1.4 test fixture only' in handler.body
        assert Path(s.row('one')['evidence']).exists()
    finally:await close(e)

@pytest.mark.asyncio
async def test_agreement_stops_before_any_form_entry_or_upload(tmp_path,local_form):
    url,handler=local_form;handler.consent=True;s=Store(tmp_path);cv=tmp_path/'cv.pdf';cv.write_bytes(b'%PDF fixture')
    s.save_config({'cv_path':str(cv)});s.put(item(url));s.authorize('one');e=Engine(s,deterministic_plan,True)
    try:
        assert await e.run(s.claim(),{'name':'Test Candidate'})=='needs_attention'
        assert handler.sent==0
        assert 'statement' in s.row('one')['reason']
    finally:await close(e)

@pytest.mark.asyncio
async def test_no_receipt_is_uncertain_and_not_a_success(tmp_path,local_form):
    url,handler=local_form;handler.receipt=False;s=Store(tmp_path);cv=tmp_path/'cv.pdf';cv.write_bytes(b'%PDF fixture')
    s.save_config({'cv_path':str(cv)});s.put(item(url));s.authorize('one');e=Engine(s,deterministic_plan,True)
    try:
        assert await e.run(s.claim(),{'name':'Test Candidate'})=='unconfirmed'
        assert handler.sent==1
        assert s.claim() is None
    finally:await close(e)


def test_revoking_standing_permissions_clears_unsent_queue_grants(tmp_path):
    s=Store(tmp_path);s.put(item());s.authorize('one',source='standing')
    s.revoke_standing()
    assert s.row('one')['state']=='awaiting_authorization'
    assert not s.authorized(s.row('one'))
    assert s.claim() is None

@pytest.mark.asyncio
async def test_no_grant_never_opens_browser_or_reads_cv(tmp_path,monkeypatch):
    s=Store(tmp_path);s.put(item());e=Engine(s)
    async def must_not_open():raise AssertionError('Browser must not open')
    monkeypatch.setattr(e,'browser',must_not_open)
    assert await e.run(s.row('one'),{'name':'private'})=='needs_attention'
    assert s.row('one')['attempted_at'] is None


def test_tracking_parameters_do_not_create_duplicate_applications(tmp_path):
    s=Store(tmp_path);s.put(item('https://careers.example.test/jobs/1?utm_source=indeed'))
    s.put(item('https://careers.example.test/jobs/1?utm_source=linkedin',ident='two'))
    assert len(s.rows())==1
    s.put(item('https://careers.example.test/jobs/1?jobId=2',ident='three'))
    assert len(s.rows())==2


@pytest.mark.asyncio
async def test_application_entry_anchor_is_navigation_not_submission(tmp_path,local_form):
    url,handler=local_form;handler.landing=True
    s=Store(tmp_path);cv=tmp_path/'cv.pdf';cv.write_bytes(b'%PDF fixture');s.save_config({'cv_path':str(cv)})
    s.put(item(url));s.authorize('one')
    async def planner(page,fields,profile):
        link=next((f for f in fields if f['tag']=='a' and f['label']=='Apply now'),None)
        if link:return {'action':'next','index':link['index']}
        return await deterministic_plan(page,fields,profile)
    engine=Engine(s,planner,True)
    try:
        assert await engine.run(s.claim(),{'name':'Test Candidate'})=='submitted',s.row('one')['reason']
        assert handler.sent==1
    finally:await close(engine)
