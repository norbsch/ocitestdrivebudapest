#!/usr/bin/env bash
# Run on the LiteLLM VM before installing LiteLLM.
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_vm
require_file deployment.env
require_file proxy/secrets/oci-api-key.pem
require_file proxy/secrets/postgres-ca.pem
step 'PostgreSQL elokeszites: helyi fajlok es fuggessegek'
mkdir -p local
chmod 700 local proxy/secrets
chmod 600 deployment.env proxy/secrets/oci-api-key.pem proxy/secrets/postgres-ca.pem
apt_install python3-venv python3-pip ca-certificates
python3 -m venv local/db-venv
local/db-venv/bin/python -m pip install --disable-pip-version-check 'psycopg[binary]>=3.2,<4'
step 'Alkalmazas DB-jelszo es helyi titkos konfiguracio'
if [[ ! -e proxy/secrets/proxy.env ]]; then
    python3 tools/write_proxy_env.py
else
    require_file proxy/secrets/proxy.env
    chmod 600 proxy/secrets/proxy.env
    printf 'Meglevo proxy.env hasznalata; a DB-jelszo es a master/salt kulcs megmarad.\n'
fi
step 'PostgreSQL: verify-full TLS, DB-felhasznalo, adatbazis es schema-jog'
local/db-venv/bin/python tools/bootstrap_database.py
printf '\nPASS: PostgreSQL elokeszitve; a 8. pont ellenorzese kovetkezik.\nLiteLLM telepites vagy modellhivas nem tortent.\n'
