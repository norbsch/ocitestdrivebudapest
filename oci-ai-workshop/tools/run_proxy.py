#!/usr/bin/env python3
"""Start native LiteLLM with private env loaded without shell evaluation."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for line in (ROOT/'proxy/secrets/proxy.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        key,value=line.split('=',1);os.environ[key]=value
venv=ROOT/'proxy/.venv/bin'
os.environ['PATH']=str(venv)+os.pathsep+os.environ.get('PATH','')
os.chdir(ROOT)
os.execv(str(venv/'litellm'),[str(venv/'litellm'),'--config',str(ROOT/'proxy/config.yaml'),'--host','0.0.0.0','--port','4000','--num_workers','1'])
