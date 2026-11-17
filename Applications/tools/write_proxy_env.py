#!/usr/bin/env python3
"""Write local proxy secrets only; no install, network call or database operation."""
import getpass
import os
from pathlib import Path
import secrets
import ssl
from urllib.parse import quote, urlencode

ROOT=Path(__file__).resolve().parents[1]


def read_env(p):
    return dict(line.split('=',1) for line in p.read_text().splitlines()
                if line and not line.startswith('#') and '=' in line)


def make_url(v,password):
    host=v['DB_HOST']
    if any(c.isspace() for c in host) or any(c in host for c in '/:@?#'):
        raise ValueError('DB_HOST must be the primary FQDN without protocol or port')
    port=int(v['DB_PORT'])
    if not 1<=port<=65535:raise ValueError('Invalid DB port')
    query=urlencode(dict(sslmode='require',sslaccept='strict',sslcert=str((ROOT/'proxy/secrets/postgres-ca.pem').resolve()),
                         connect_timeout=10,connection_limit=5,pool_timeout=15))
    return f"postgresql://{quote(v['DB_USER'],safe='')}:{quote(password,safe='')}@{host}:{port}/{quote(v['DB_NAME'],safe='')}?{query}"


def main():
    out=ROOT/'proxy/secrets/proxy.env'
    if out.exists():raise SystemExit('proxy.env already exists; not overwritten. Edit it in place for planned changes.')
    v=read_env(ROOT/'deployment.env')
    if any(not x or 'REPLACE' in x for x in v.values()):raise SystemExit('Fill every deployment.env placeholder first.')
    for k in ['LITELLM_PRIVATE_IP','APP_01_PRIVATE_IP','APP_02_PRIVATE_IP','DB_HOST','DB_PORT','DB_USER','DB_NAME','OCI_REGION','OCI_COMPARTMENT_ID','OCI_USER','OCI_TENANCY','OCI_FINGERPRINT','OCI_MODEL_ID']:
        if not v.get(k):raise SystemExit('Missing deployment.env field: '+k)
    if v['DB_NAME']!='litellm' or v['DB_USER']!='litellm':raise SystemExit('This guide uses DB_NAME=litellm and DB_USER=litellm throughout.')
    key=ROOT/'proxy/secrets/oci-api-key.pem';ca=ROOT/'proxy/secrets/postgres-ca.pem'
    if not key.is_file() or not ca.is_file():raise SystemExit('Copy OCI API private key and public DB CA first.')
    ssl.create_default_context(cafile=str(ca))
    password=getpass.getpass('Password of the litellm DB user (not DB admin): ')
    if not password or password!=getpass.getpass('Repeat litellm DB password: '):raise SystemExit('Empty or differing passwords; nothing written.')
    env={k:v[k] for k in ['OCI_REGION','OCI_COMPARTMENT_ID','OCI_USER','OCI_TENANCY','OCI_FINGERPRINT','OCI_MODEL_ID']}
    env.update(OCI_KEY_FILE=str((ROOT/'proxy/secrets/oci-api-key.pem').resolve()),DATABASE_URL=make_url(v,password),
               LITELLM_MASTER_KEY='sk-'+secrets.token_hex(32),LITELLM_SALT_KEY=secrets.token_hex(32),
               UI_USERNAME='admin',UI_PASSWORD=secrets.token_hex(24),
               STORE_MODEL_IN_DB='False')
    fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(''.join(k+'='+value+'\n' for k,value in env.items()))
    print('proxy/secrets/proxy.env created (0600). Secrets not printed. No remote operation performed.')


if __name__=='__main__':
    main()
