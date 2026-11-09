import json
import os
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode

TERMINAL={'submitted','unconfirmed','needs_attention','awaiting_authorization'}

def scope_matches(url, prefix):
    a,b=urlsplit(url),urlsplit(prefix)
    return a.scheme==b.scheme and a.netloc.lower()==b.netloc.lower() and (a.path==b.path or a.path.startswith(b.path.rstrip('/')+'/'))

def posting_url_key(url):
    u=urlsplit(url)
    pairs=[(k,v) for k,v in parse_qsl(u.query,keep_blank_values=True)
           if not k.lower().startswith('utm_') and k.lower() not in ('gh_src','lever-source','trackingid','trk')]
    return urlunsplit((u.scheme.lower(),u.netloc.lower(),u.path.rstrip('/'),urlencode(sorted(pairs)),''))

class Store:
    def __init__(self, directory=None):
        self.root=Path(directory or os.getenv('JN_AUTOPILOT_DIR','.personal/autopilot')).resolve()
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.root.chmod(0o700)
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS queue(
                job_id TEXT PRIMARY KEY, company TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
                state TEXT NOT NULL, authorization TEXT, reason TEXT DEFAULT '', evidence TEXT DEFAULT '',
                submitted_at REAL, attempted_at REAL, updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS queue_url ON queue(url);''')
    def db(self):
        db=sqlite3.connect(self.root/'queue.sqlite',timeout=10)
        db.row_factory=sqlite3.Row
        return db
    def config(self):
        defaults={'enabled':False,'min_score':70,'max_per_six_hours':10,'cv_path':'','employers':[]}
        with self.db() as db:
            row=db.execute("SELECT value FROM settings WHERE key='config'").fetchone()
        if row:defaults.update(json.loads(row[0]))
        return defaults
    def save_config(self,value):
        cfg=self.config();cfg.update(value)
        if not 1<=int(cfg['max_per_six_hours'])<=10:raise ValueError('Limit must be 1–10')
        with self.db() as db:db.execute("INSERT OR REPLACE INTO settings VALUES('config',?)",(json.dumps(cfg),))
    def put(self,job):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if any(posting_url_key(r[0])==posting_url_key(job['url']) for r in db.execute('SELECT url FROM queue')):
                return
            db.execute('INSERT OR IGNORE INTO queue(job_id,company,title,url,state,updated) VALUES(?,?,?,?,?,?)',
                       (job['job_id'],job['company'],job['title'],job['url'],'awaiting_authorization',time.time()))
    def rows(self):
        with self.db() as db:return [dict(r) for r in db.execute('SELECT * FROM queue ORDER BY updated DESC')]
    def row(self,ident):
        with self.db() as db:
            r=db.execute('SELECT * FROM queue WHERE job_id=?',(ident,)).fetchone()
            return dict(r) if r else None
    def authorize(self,ident,source="job"):
        row=self.row(ident)
        if not row:raise ValueError('Unknown job')
        if row['attempted_at'] or row['state'] in ('running','submitting','submitted','unconfirmed'):raise ValueError('Already sent or uncertain; do not retry')
        grant={'company':row['company'],'url':row['url'],'cv':True,'contact':True,'answers':True,'submit':True,'at':time.time(),'source':source}
        with self.db() as db:db.execute("UPDATE queue SET authorization=?,state='queued',reason='',updated=? WHERE job_id=?",
                                      (json.dumps(grant),time.time(),ident))
    def revoke_standing(self):
        with self.db() as db:
            for row in self.rows():
                if json.loads(row['authorization'] or '{}').get('source')=='standing' and not row['attempted_at']:
                    state='awaiting_authorization' if row['state']=='queued' else row['state']
                    db.execute('UPDATE queue SET authorization=NULL,state=? WHERE job_id=?',(state,row['job_id']))
    def authorized(self,row):
        a=json.loads(row['authorization'] or '{}')
        return a.get('company')==row['company'] and a.get('url')==row['url'] and all(a.get(k) is True for k in ('cv','contact','answers','submit'))
    def transition(self,ident,state,reason='',evidence=''):
        with self.db() as db:db.execute('UPDATE queue SET state=?,reason=?,evidence=?,updated=? WHERE job_id=?',
                                      (state,reason,evidence,time.time(),ident))
    def claim(self):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM queue WHERE state='queued' AND attempted_at IS NULL ORDER BY updated LIMIT 1").fetchone()
            if not row:return None
            db.execute("UPDATE queue SET state='running',updated=? WHERE job_id=?",(time.time(),row['job_id']))
            return dict(row)
    def remaining(self):
        with self.db() as db:
            n=db.execute('SELECT count(*) FROM queue WHERE attempted_at>?',(time.time()-21600,)).fetchone()[0]
        return max(0,self.config()['max_per_six_hours']-n)
    def mark_attempt(self,ident):
        with self.db() as db:
            count=db.execute('SELECT count(*) FROM queue WHERE attempted_at>?',(time.time()-21600,)).fetchone()[0]
            if count>=self.config()['max_per_six_hours']:raise ValueError('Six-hour submission limit reached')
            cur=db.execute("UPDATE queue SET attempted_at=?,state='submitting',updated=? WHERE job_id=? AND attempted_at IS NULL",
                           (time.time(),time.time(),ident))
            if cur.rowcount!=1:raise ValueError('A submission was already attempted')
    def recover(self):
        # A lost response after a click must NEVER cause an automatic repeat submission.
        with self.db() as db:
            db.execute("UPDATE queue SET state='unconfirmed',reason='Restart after submission attempt: verify receipt manually' WHERE state IN ('running','submitting') AND attempted_at IS NOT NULL")
            db.execute("UPDATE queue SET state='queued' WHERE state='running' AND attempted_at IS NULL")
    def resume(self,ident):
        r=self.row(ident)
        if not r or r['state']!='needs_attention' or r['attempted_at']:raise ValueError('This item cannot safely be resumed')
        self.transition(ident,'queued')
