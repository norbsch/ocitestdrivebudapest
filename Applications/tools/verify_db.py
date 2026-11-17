#!/usr/bin/env python3
"""Run on LiteLLM VM using proxy/.venv/bin/python. Read-only DB verification."""
import asyncio
import json
import os
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
for line in (ROOT/'proxy/secrets/proxy.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);os.environ[k]=v
from prisma import Prisma

async def main():
    db=Prisma();await db.connect()
    try:
        who=await db.query_raw('SELECT current_database() AS database, current_user AS username')
        tls=await db.query_raw('SELECT ssl, version FROM pg_stat_ssl WHERE pid=pg_backend_pid()')
        migrations=await db.query_raw('SELECT count(*)::int AS applied FROM "_prisma_migrations" WHERE finished_at IS NOT NULL AND rolled_back_at IS NULL')
        failed=await db.query_raw('SELECT count(*)::int AS unfinished FROM "_prisma_migrations" WHERE finished_at IS NULL AND rolled_back_at IS NULL')
        assert who[0]['database']=='litellm' and who[0]['username']=='litellm'
        assert tls[0]['ssl'] and migrations[0]['applied']>0 and failed[0]['unfinished']==0
        print(json.dumps(dict(identity=who,tls=tls,migrations=migrations,failed=failed)))
        callid=os.environ.get('CHECK_CALL_ID','')
        if callid:
            if not re.fullmatch('[a-zA-Z0-9-]{1,100}',callid):raise ValueError('Invalid call id')
            rows=await db.query_raw('SELECT request_id, litellm_call_id, model, spend, prompt_tokens, completion_tokens FROM "LiteLLM_SpendLogs" WHERE litellm_call_id=$1',callid)
            if not rows:raise RuntimeError('Spend row not visible yet; wait for async log write and rerun this read-only check')
            assert rows[0]['spend']>0
            print(json.dumps(dict(spend_log=rows),default=str))
            print('PASS: exact inference call found in managed PostgreSQL.')
        else:print('PASS: Prisma SQL connection, TLS and migration state.')
    finally:await db.disconnect()

try:asyncio.run(main())
except Exception as exc:raise SystemExit('FAIL '+type(exc).__name__+': check connection/migrations or async spend logging; raw driver details withheld.')
