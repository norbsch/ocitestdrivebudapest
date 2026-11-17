#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_vm
require_file deployment.env
require_file proxy/secrets/oci-api-key.pem
require_file proxy/secrets/postgres-ca.pem
require_file templates/litellm.service
require_file proxy/secrets/proxy.env
[[ -x local/db-venv/bin/python ]] || fail 'Elobb futtasd a 7.5 pontot: bash scripts/prepare_postgres.sh'
step 'Konfiguracio ellenorzese'
python3 - <<'PY'
import ipaddress
from pathlib import Path
from tools.write_proxy_env import read_env
v = read_env(Path('deployment.env'))
for k in ['LITELLM_PRIVATE_IP', 'APP_01_PRIVATE_IP', 'APP_02_PRIVATE_IP', 'DB_HOST', 'DB_PORT', 'DB_ADMIN', 'DB_NAME', 'DB_USER', 'OCI_REGION', 'OCI_COMPARTMENT_ID', 'OCI_USER', 'OCI_TENANCY', 'OCI_FINGERPRINT', 'OCI_MODEL_ID']:
    if not v.get(k) or 'REPLACE' in v[k]: raise SystemExit('Toltsd ki: ' + k)
ips = [ipaddress.IPv4Address(v[k]) for k in ['LITELLM_PRIVATE_IP', 'APP_01_PRIVATE_IP', 'APP_02_PRIVATE_IP']]
if len(set(ips)) != 3: raise SystemExit('A harom VM IP-je legyen kulonbozo.')
PY
chmod 600 deployment.env proxy/secrets/oci-api-key.pem proxy/secrets/postgres-ca.pem
mkdir -p local
chmod 700 local proxy/secrets
chmod 600 proxy/secrets/proxy.env
step 'PostgreSQL elofeltetel: csak olvasasi ellenorzes'
local/db-venv/bin/python tools/bootstrap_database.py --check-only
check_port 4000 litellm
step 'Ubuntu csomagok es Python kornyezet'
apt_install python3-venv python3-pip postgresql-client nodejs npm libatomic1 libsndfile1 curl ca-certificates openssl iptables-persistent
python3 -m venv proxy/.venv
proxy/.venv/bin/python -m pip install --disable-pip-version-check -r proxy/requirements.txt
step 'OCI API-kulcs fingerprint es CA ellenorzese'
python3 - <<'PYCERT'
import hashlib
from pathlib import Path
import subprocess
from tools.write_proxy_env import read_env
v = read_env(Path('deployment.env'))
pub = subprocess.check_output(['openssl', 'pkey', '-in', 'proxy/secrets/oci-api-key.pem', '-pubout', '-outform', 'DER'])
actual = ':'.join(hashlib.md5(pub).hexdigest()[i:i+2] for i in range(0, 32, 2))
if actual.lower() != v['OCI_FINGERPRINT'].lower(): raise SystemExit('Az OCI API-kulcs fingerprintje nem egyezik a deployment.env ertekevel.')
subprocess.run(['openssl', 'x509', '-in', 'proxy/secrets/postgres-ca.pem', '-checkend', '0', '-noout'], check=True)
print('PASS: OCI fingerprint es CA ervenyesseg')
PYCERT
step 'Prisma kliens generalasa'
SCHEMA="$(proxy/.venv/bin/python -c 'import importlib.util; from pathlib import Path; print(Path(importlib.util.find_spec("litellm_proxy_extras").origin).parent/"schema.prisma")')"
PATH="$WORKSHOP_ROOT/proxy/.venv/bin:$PATH" proxy/.venv/bin/prisma generate --schema="$SCHEMA"
step 'VM tuzfal: mindket app -> LiteLLM:4000'
mapfile -t APP_IPS < <(python3 - <<'PY'
from pathlib import Path
from tools.write_proxy_env import read_env
v = read_env(Path('deployment.env'))
print(v['APP_01_PRIVATE_IP'])
print(v['APP_02_PRIVATE_IP'])
PY
)
allow_tcp 4000 "${APP_IPS[0]}"
allow_tcp 4000 "${APP_IPS[1]}"
sudo netfilter-persistent save
step 'LiteLLM szolgaltatas inditasa es ellenorzese'
install_unit litellm
python3 tools/wait_service.py litellm
proxy/.venv/bin/python tools/verify_db.py
printf '\nPASS: LiteLLM telepitve, TLS/adatbazis es migraciok ellenorizve.\nA kovetkezo guide-lepes az app virtualis kulcsanak letrehozasa. Modellhivas nem tortent.\n'
