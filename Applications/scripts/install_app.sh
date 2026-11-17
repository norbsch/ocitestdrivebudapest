#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_vm
require_file app/.env
require_file templates/streamlit-app.service
step 'App konfiguracio ellenorzese'
python3 - <<'PY'
from pathlib import Path
from urllib.parse import urlsplit
from tools.write_proxy_env import read_env
v = read_env(Path('app/.env'))
for k in ['LITELLM_BASE_URL', 'LITELLM_API_KEY', 'LITELLM_MODEL', 'STREAMLIT_SERVER_COOKIE_SECRET']:
    if not v.get(k) or 'REPLACE' in v[k]: raise SystemExit('Hianyzo app/.env mezo: ' + k)
u = urlsplit(v['LITELLM_BASE_URL'])
if u.scheme != 'http' or not u.hostname or u.port != 4000 or u.username or u.password:
    raise SystemExit('A LiteLLM URL formatuma http://PRIVAT_IP:4000 legyen.')
if len(v['STREAMLIT_SERVER_COOKIE_SECRET']) < 32: raise SystemExit('Tul rovid cookie secret.')
PY
chmod 600 app/.env
check_port 80 streamlit-app
step 'Ubuntu csomagok es Streamlit fuggosegek'
apt_install python3-venv python3-pip curl ca-certificates iptables-persistent
python3 -m venv app/.venv
app/.venv/bin/python -m pip install --disable-pip-version-check -r app/requirements.txt
step 'App -> LiteLLM halozati proba'
python3 tools/wait_service.py upstream
step 'VM tuzfal es Streamlit inditasa a 80-as porton'
allow_tcp 80
sudo netfilter-persistent save
install_unit streamlit-app
python3 tools/wait_service.py app
printf '\nPASS: Streamlit telepitve es aktiv HTTP/80-on, LiteLLM elerheto.\nUgyanezt a scriptet futtasd a masik app VM-en is. Modellhivas nem tortent.\n'
