"""Cross-process admission, bounded fair queues and session-wide Jev budget.

SQLite stores scheduling metadata only. Keys, images and input traces never enter
the ledger. Each process performs its admitted HTTP call on its own worker.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid
from contextlib import contextmanager

class JevBroker:
    def __init__(self, path=None, session=None, clock=time.time, cooldown=30., cap=30):
        self.path = Path(path or Path(__file__).resolve().parents[1]/'.runtime'/'jev-budget.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.session = session or os.environ.get('KT_COACH_SESSION', 'standalone')
        self.clock=clock; self.cooldown=cooldown; self.cap=cap
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS budget(session TEXT PRIMARY KEY, attempts INTEGER,
              last REAL, lease TEXT, until_at REAL, last_domain TEXT, backoff REAL);
              CREATE TABLE IF NOT EXISTS queue(session TEXT, domain TEXT, key TEXT, created REAL,
              expires REAL, PRIMARY KEY(session,domain,key));''')
            db.execute('INSERT OR IGNORE INTO budget VALUES (?,0,-1e20,NULL,0,\'\',0)', (self.session,))

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path, timeout=.2)
        try:
            with db:yield db
        finally:db.close()

    def acquire(self, domain, key, lifetime=3.):
        now=self.clock()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM queue WHERE expires < ?', (now,))
            row=db.execute('SELECT attempts,last,lease,until_at,last_domain,backoff FROM budget WHERE session=?',(self.session,)).fetchone()
            attempts,last,lease,until,previous,backoff=row
            db.execute('INSERT OR IGNORE INTO queue VALUES (?,?,?,?,?)',(self.session,domain,key,now,now+lifetime))
            db.execute('DELETE FROM queue WHERE rowid IN (SELECT rowid FROM queue WHERE session=? AND domain=? ORDER BY created DESC LIMIT -1 OFFSET 8)',(self.session,domain))
            first=db.execute('SELECT domain,key FROM queue WHERE session=? ORDER BY (domain=?) ASC,created ASC LIMIT 1',(self.session,previous)).fetchone()
            if attempts>=self.cap or now<backoff or now-last<self.cooldown or (lease and now<until) or first!=(domain,key):return None
            token=uuid.uuid4().hex
            db.execute('UPDATE budget SET attempts=attempts+1,last=?,lease=?,until_at=?,last_domain=? WHERE session=?',(now,token,now+60,domain,self.session))
            db.execute('DELETE FROM queue WHERE session=? AND domain=? AND key=?',(self.session,domain,key))
            return token

    def finish(self, token, backoff=0):
        with self.connect() as db:
            db.execute('UPDATE budget SET lease=NULL,until_at=0,backoff=? WHERE session=? AND lease=?',
                       (self.clock()+backoff,self.session,token))

    def attempts(self):
        with self.connect() as db:return db.execute('SELECT attempts FROM budget WHERE session=?',(self.session,)).fetchone()[0]

    @staticmethod
    def key(domain, state, questions):
        return hashlib.sha256(json.dumps([domain,state,questions],sort_keys=True).encode()).hexdigest()
