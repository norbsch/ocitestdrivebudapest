#!/usr/bin/env python3
"""Explicit health, key and inference steps. Passwords/tokens are never printed."""
import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]


def read_env(p):
    return dict(line.split('=',1) for line in p.read_text().splitlines()
                if line and not line.startswith('#') and '=' in line)


def call(base,token,path,body=None):
    req=urllib.request.Request(base.rstrip('/')+path,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},
                               data=None if body is None else json.dumps(body).encode())
    # Local admin calls never go through workstation/enterprise HTTP proxies.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req,timeout=150) as r:return json.load(r),r.headers


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['health','create-key','spend','smoke'])
    p.add_argument('--url',default='http://127.0.0.1:4000')
    p.add_argument('--alias',default='streamlit-workshop')
    p.add_argument('--budget',type=float,default=10)
    a=p.parse_args()
    env=read_env(ROOT/'proxy/secrets/proxy.env')
    out=ROOT/'local/streamlit.env'
    if a.action=='health':
        for path in ['/health/liveliness','/health/readiness']:
            call(a.url,env['LITELLM_MASTER_KEY'],path);print('PASS '+path)
    elif a.action=='create-key':
        if out.exists():raise SystemExit('local/streamlit.env already exists. Reuse it; do not create another key blindly.')
        if a.budget<=0:raise SystemExit('Budget must be positive')
        v=read_env(ROOT/'deployment.env')
        out.parent.mkdir(mode=0o700,exist_ok=True)
        fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        # Reserve output first, so an existing file cannot be clobbered after key creation.
        try:
            data,_=call(a.url,env['LITELLM_MASTER_KEY'],'/key/generate',dict(models=['oci-cohere'],key_alias=a.alias,max_budget=a.budget,rpm_limit=10))
            with os.fdopen(fd,'w') as f:
                f.write(f'LITELLM_BASE_URL=http://{v["LITELLM_PRIVATE_IP"]}:4000\nLITELLM_API_KEY={data["key"]}\nLITELLM_MODEL=oci-cohere\n')
        except Exception:
            try:os.close(fd)
            except OSError:pass
            # A failed/uncertain remote key creation is not retried automatically.
            raise SystemExit('Key operation failed or outcome uncertain. Output file retained; inspect proxy before retrying.')
        print('PASS key created; secret saved to local/streamlit.env (0600), not displayed.')
    else:
        app=read_env(out)
        if a.action=='spend':
            data,_=call(a.url,app['LITELLM_API_KEY'],'/key/info');info=data['info']
            print(json.dumps({k:info.get(k) for k in ['key_alias','models','spend','max_budget']},indent=2))
        else:
            data,headers=call(a.url,app['LITELLM_API_KEY'],'/v1/chat/completions',dict(model='oci-cohere',messages=[dict(role='user',content='Válaszolj egy szóval: működik?')],max_tokens=32,stream=False))
            result=dict(answer=data['choices'][0]['message']['content'],usage=data.get('usage'),cost_usd=headers.get('x-litellm-response-cost'),
                        litellm_call_id=headers.get('x-litellm-call-id'),completion_id=data.get('id'))
            dest=ROOT/'local/smoke-result.json';dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');dest.chmod(0o600)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            if result['cost_usd'] is None or Decimal(result['cost_usd'])<=0:raise SystemExit('FAIL missing/zero cost: verify price configuration; do not repeat inference automatically.')


if __name__=='__main__':
    try:main()
    except urllib.error.HTTPError as e:raise SystemExit(f'HTTP {e.code}; inspect proxy logs locally. Response body withheld.')
    except (OSError,ValueError,KeyError,TimeoutError):raise SystemExit('Check local config, proxy address and credential validity. No secret values printed; no automatic retry.')
