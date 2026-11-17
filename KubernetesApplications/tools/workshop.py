#!/usr/bin/env python3
"""Cloud Shell installer. Explicit actions; credentials never enter command arguments."""
import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import ssl
import subprocess
import time

from manifests import PART, all_manifests, images, labels, resource

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / 'local'


def fail(message):
    raise SystemExit('HIBA: ' + message)


def private_write(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def settings(require_context=True):
    source = ROOT / 'settings.env'
    if not source.is_file(): fail('Masold le a templates/settings.env.example fajlt settings.env neven es toltsd ki.')
    result = {}
    for line in source.read_text().splitlines():
        if line and not line.startswith('#'):
            key, sep, value = line.partition('=')
            if not sep or key != key.strip() or key in result: fail('Hibas vagy ismetelt settings.env sor.')
            result[key] = value.strip()
    required = ['KUBE_CONTEXT', 'NAMESPACE', 'REGISTRY', 'OCIR_NAMESPACE', 'OCIR_USERNAME',
        'APP_REPOSITORY', 'PROXY_REPOSITORY', 'IMAGE_TAG', 'NODE_PORT', 'APP_PUBLIC_HOST', 'APP_PUBLIC_PORT', 'DB_HOST', 'DB_PORT',
        'DB_NAME', 'DB_USER', 'DB_ADMIN', 'OCI_REGION', 'OCI_COMPARTMENT_ID', 'OCI_USER',
        'OCI_TENANCY', 'OCI_FINGERPRINT', 'OCI_MODEL_ID']
    for key in required:
        if key == 'KUBE_CONTEXT' and not require_context: continue
        if not result.get(key) or 'REPLACE' in result[key]: fail('Toltsd ki: ' + key)
    for key in ['NAMESPACE', 'APP_REPOSITORY', 'PROXY_REPOSITORY']:
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', result[key]): fail('Ervenytelen nev: ' + key)
    if result['NAMESPACE'] in ['default', 'kube-system', 'kube-public', 'kube-node-lease']:
        fail('Kulon workshop namespace-t valassz.')
    for key in ['DB_USER', 'DB_NAME', 'DB_ADMIN']:
        if not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}', result[key]): fail('Egyszeru kisbetus PostgreSQL-nev szukseges: ' + key)
    for key in ['REGISTRY', 'DB_HOST', 'APP_PUBLIC_HOST']:
        if not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', result[key]): fail('Csak hostnev, protokoll/port nelkul: ' + key)
    if not re.fullmatch(r'[a-z0-9]+', result['OCIR_NAMESPACE']): fail('Ervenytelen OCIR tenancy namespace.')
    if not re.fullmatch(r'[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}', result['IMAGE_TAG']): fail('Ervenytelen kep-tag.')
    if not 30000 <= int(result['NODE_PORT']) <= 32767: fail('A NodePort a 30000-32767 tartomanyban legyen.')
    if not 1 <= int(result['APP_PUBLIC_PORT']) <= 65535: fail('Ervenytelen publikus app-port.')
    if not 1 <= int(result['DB_PORT']) <= 65535: fail('Ervenytelen DB-port.')
    if not re.fullmatch(r'(?:[a-fA-F0-9]{2}:){15}[a-fA-F0-9]{2}', result['OCI_FINGERPRINT']): fail('Ervenytelen OCI fingerprint.')
    return result


def run(command, input=None, capture=True, check=True):
    completed = subprocess.run(command, input=input, text=True,
        stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None)
    if check and completed.returncode:
        # API/driver output can contain credentials; do not replay it.
        fail(command[0] + ' muvelet sikertelen. A guide hibakeresesi lepeseivel ellenorizd; titkos kimenet nincs kiirva.')
    return completed


class Cluster:
    def __init__(self, values):
        self.v = values

    def command(self, args, **kwargs):
        return run(['kubectl', '--context', self.v['KUBE_CONTEXT'], '-n', self.v['NAMESPACE']] + args, **kwargs)

    def get(self, kind, name):
        value = self.command(['get', kind, name, '--ignore-not-found', '-o', 'json', '--request-timeout=20s']).stdout
        return json.loads(value) if value.strip() else None

    def apply(self, obj):
        self.command(['apply', '--server-side', '--field-manager=oci-ai-kubernetes', '-f', '-'], input=json.dumps(obj))

    def ensure_namespace(self):
        obj = self.get('namespace', self.v['NAMESPACE'])
        if obj and obj['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != PART:
            fail('A namespace mar letezik, de nem ehhez a csomaghoz tartozik. Valassz uj nevet.')
        self.apply(all_manifests(self.v)['namespace'])

    def ensure_owned(self):
        obj = self.get('namespace', self.v['NAMESPACE'])
        if not obj or obj['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != PART:
            fail('Elobb a prepare muveletet futtasd a sajat namespace letrehozasahoz.')

    def secret(self, name, values, secret_type='Opaque', replace=False):
        obj = resource('Secret', name, self.v['NAMESPACE'])
        obj['type'] = secret_type
        obj['data'] = {key: base64.b64encode(value.encode()).decode() for key, value in values.items()}
        current = self.get('secret', name)
        if current and current.get('data') != obj['data'] and not replace:
            fail('Meglevo Secret elter: ' + name + '. Nem irjuk felul; egyeztesd a mentett hitelesitoket.')
        self.apply(obj)

    def exec_proxy(self, script, args=(), input=None):
        return self.command(['exec'] + (['-i'] if input is not None else []) +
            ['deployment/litellm', '--', 'python', '/opt/workshop/runtime/' + script] + list(args), input=input)

    def run_job(self, obj):
        name = obj['metadata']['name']
        previous = self.get('job', name)
        if previous:
            if previous.get('status', {}).get('active'):
                fail('A Job meg fut: ' + name + '; ne inditsd parhuzamosan.')
            self.command(['delete', 'job', name, '--wait=true', '--timeout=60s'])
        self.apply(obj)
        print('Varakozas: ' + name, flush=True)
        deadline = time.monotonic() + 660
        next_update = 0
        while time.monotonic() < deadline:
            current = self.get('job', name)
            status = current.get('status', {}) if current else {}
            if status.get('succeeded'):
                print('PASS: ' + name)
                return
            if status.get('failed') or any(c.get('type') == 'Failed' and c.get('status') == 'True' for c in status.get('conditions', [])):
                fail('Job hibas: ' + name + '. Nezd meg helyben: kubectl -n ' + self.v['NAMESPACE'] + ' logs job/' + name)
            if time.monotonic() >= next_update:
                print('  A Job meg nem fejezodott be; pod/status ellenorzes folyamatban.', flush=True)
                next_update = time.monotonic() + 30
            time.sleep(3)
        fail('Job idotullepes: ' + name + '. Ellenorizd a podokat es a naplot; nincs automatikus ujraprobalas.')


def preflight(v, cluster):
    if run(['kubectl', 'config', 'current-context']).stdout.strip() != v['KUBE_CONTEXT']:
        fail('Az aktiv kubectl context elter a settings.env KUBE_CONTEXT erteketol. Egyeztesd, melyik clusteren dolgozol.')
    nodes = json.loads(cluster.command(['get', 'nodes', '-o', 'json', '--request-timeout=15s']).stdout)['items']
    ready = [n for n in nodes if n['metadata'].get('labels', {}).get('kubernetes.io/arch') == 'amd64'
             and any(c['type'] == 'Ready' and c['status'] == 'True' for c in n.get('status', {}).get('conditions', []))
             and not n.get('spec', {}).get('unschedulable', False)]
    if not ready: fail('Nincs utemezheto Ready amd64 worker node.')
    services = json.loads(cluster.command(['get', 'services', '-A', '-o', 'json']).stdout)['items']
    for service in services:
        for port in service.get('spec', {}).get('ports', []):
            if port.get('nodePort') == int(v['NODE_PORT']) and (service['metadata']['namespace'], service['metadata']['name']) != (v['NAMESPACE'], 'streamlit'):
                fail('A valasztott NodePort mar foglalt; allits masik NODE_PORT erteket.')
    print('PASS: context, Ready amd64 node es NodePort ellenorizve.')


def build_push(v):
    if platform.machine().lower() not in ['x86_64', 'amd64']:
        fail('A Cloud Shell Architecture legyen x86_64, majd inditsd ujra a sessiont.')
    if not shutil.which('podman'): fail('A buildhez Podman szukseges; ezt a Cloud Shell biztositja.')
    refs = images(v)
    token = getpass.getpass('OCI Auth Token az OCIR-hez (nem API-kulcs / Console-jelszo): ')
    if not token: fail('Ures OCIR token.')
    auth = {'auths': {v['REGISTRY']: {'auth': base64.b64encode((v['OCIR_NAMESPACE'] + '/' + v['OCIR_USERNAME'] + ':' + token).encode()).decode()}}}
    path = LOCAL / 'registry-auth.json'
    if path.exists(): path.unlink()
    private_write(path, auth)
    for key, dockerfile in [('APP', 'app/Dockerfile'), ('PROXY', 'proxy/Dockerfile')]:
        print('Kontener build: ' + key, flush=True)
        run(['podman', 'build', '--authfile', str(path), '--platform', 'linux/amd64',
             '-f', str(ROOT / dockerfile), '-t', refs[key], str(ROOT)], capture=False)
        actual = run(['podman', 'image', 'inspect', '--format', '{{.Architecture}}', refs[key]]).stdout.strip()
        if actual != 'amd64': fail('A build nem amd64 kepet eredmenyezett.')
        run(['podman', 'push', '--authfile', str(path), refs[key]], capture=False)
    print('PASS: ket kep az OCIR-ben. A registry-auth.json titkos fajl, ne tedd Gitbe.')


def prepare(v, cluster):
    preflight(v, cluster)
    key_path, ca_path = LOCAL / 'oci-api-key.pem', LOCAL / 'postgres-ca.pem'
    if not key_path.is_file() or not ca_path.is_file(): fail('Tedd az OCI API privat kulcsot es a DB CA-t a local/ konyvtarba; guide 5. pont.')
    for path in [key_path, ca_path]: path.chmod(0o600)
    ssl.create_default_context(cafile=str(ca_path))
    # Empty passphrase prevents an unexpected interactive OpenSSL prompt.
    public = subprocess.run(['openssl', 'pkey', '-in', str(key_path), '-passin', 'pass:', '-pubout', '-outform', 'DER'], capture_output=True)
    if public.returncode: fail('Az OCI API-kulcs nem olvashato vagy titkositott; ellenorizd a fajlt.')
    actual = ':'.join(re.findall('..', hashlib.md5(public.stdout).hexdigest()))
    if actual.lower() != v['OCI_FINGERPRINT'].lower(): fail('Az API-kulcs fingerprintje nem egyezik.')
    auth_path = LOCAL / 'registry-auth.json'
    if not auth_path.is_file(): fail('Elobb futtasd a build-push muveletet az OCIR hitelesiteshez.')
    cluster.ensure_namespace()
    state_path = LOCAL / 'credentials.json'
    identity = {k: v[k] for k in ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER']}
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state['database'] != identity: fail('A DB-cel megvaltozott a mentett hitelesitokhoz kepest. Ne irj felul futo telepitest; egyeztesd az atallast.')
    else:
        if cluster.get('secret', 'litellm-auth'): fail('A clusterben mar vannak kulcsok. Allitsd vissza a hozza tartozo local/ mentest; nem generalunk ujat.')
        password = getpass.getpass('Alkalmazas PostgreSQL-jelszava: ')
        if not password or password != getpass.getpass('Alkalmazas PostgreSQL-jelszava ismet: '): fail('Ures vagy eltero jelszavak.')
        state = dict(database=identity, auth=dict(DB_PASSWORD=password, LITELLM_MASTER_KEY='sk-' + secrets.token_hex(32),
            LITELLM_SALT_KEY=secrets.token_hex(32), UI_USERNAME='admin', UI_PASSWORD=secrets.token_hex(24)))
        private_write(state_path, state)
    state_path.chmod(0o600)
    cluster.secret('litellm-auth', state['auth'])
    cluster.secret('oci-api-key', {'oci-api-key.pem': key_path.read_text()})
    cluster.secret('ocir-pull', {'.dockerconfigjson': auth_path.read_text()}, 'kubernetes.io/dockerconfigjson', replace=True)
    for name, data in [('workshop-config', {k: v[k] for k in ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_ADMIN',
        'OCI_REGION', 'OCI_COMPARTMENT_ID', 'OCI_USER', 'OCI_TENANCY', 'OCI_FINGERPRINT', 'OCI_MODEL_ID']}),
        ('postgres-ca', {'postgres-ca.pem': ca_path.read_text()}),
        ('litellm-config', {'config.yaml': (ROOT / 'proxy/config.yaml').read_text()})]:
        obj = resource('ConfigMap', name, v['NAMESPACE'])
        obj['data'] = data
        cluster.apply(obj)
    print('PASS: namespace, ConfigMapek es Secretek elokeszitve. DB-letrehozas vagy modellhivas nem tortent.')


def create_app_key(v, cluster):
    path = LOCAL / 'streamlit-auth.json'
    marker = LOCAL / 'key-create-attempt.json'
    if not path.exists():
        if marker.exists() or cluster.get('secret', 'streamlit-auth'):
            fail('Korabbi kulcsletrehozas van/eredmenye bizonytalan. Ne hozz letre uj kulcsot vakon; ellenorizd a LiteLLM kulcslistat es a local/ mentest.')
        private_write(marker, {'alias': v['NAMESPACE'] + '-streamlit'})
        answer = cluster.exec_proxy('admin.py', ['create-key'])
        result = json.loads(answer.stdout)
        if not isinstance(result.get('key'), str) or not result['key'].startswith('sk-'):
            fail('A kulcsletrehozas eredmenye nem ertelmezheto; nincs automatikus ujraprobalas.')
        private_write(path, {'LITELLM_API_KEY': result['key'], 'STREAMLIT_SERVER_COOKIE_SECRET': secrets.token_hex(32)})
    cluster.secret('streamlit-auth', json.loads(path.read_text()))
    print('PASS: app virtualis kulcs (10 USD, 10 RPM), a titok csak a local/ fajlban es a Kubernetes Secretben van.')


def render(v):
    dest = LOCAL / 'rendered'
    dest.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name, obj in all_manifests(v).items():
        (dest / (name + '.json')).write_text(json.dumps(obj, indent=2) + '\n')
    print('PASS: nem titkos Kubernetes manifestek a local/rendered/ konyvtarban.')


def main(argv=None):
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['render', 'check', 'build-push', 'prepare', 'prepare-db', 'init-db',
        'deploy-litellm', 'create-app-key', 'deploy-app', 'verify', 'smoke', 'verify-spend', 'status'])
    args = parser.parse_args(argv)
    v = settings(require_context=args.action != 'build-push')
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    LOCAL.chmod(0o700)
    cluster = Cluster(v)
    manifests = all_manifests(v)
    if args.action == 'render': render(v); return
    if args.action == 'build-push': build_push(v); return
    if args.action == 'check': preflight(v, cluster); return
    if args.action == 'prepare': prepare(v, cluster); return
    cluster.ensure_owned()
    if args.action == 'prepare-db': cluster.run_job(manifests['db-check'])
    elif args.action == 'init-db':
        old = cluster.get('job', 'db-init-db')
        if old and old.get('status', {}).get('active'): fail('A DB-admin Job mar fut.')
        password = getpass.getpass('PostgreSQL DB-admin jelszava (' + v['DB_ADMIN'] + '): ')
        if not password: fail('Ures DB-admin jelszo.')
        cluster.secret('db-admin-once', {'DB_ADMIN_PASSWORD': password}, replace=True)
        try:
            cluster.run_job(manifests['db-init'])
        except SystemExit:
            logs = cluster.command(['logs', 'job/db-init-db'], check=False).stdout
            # The DB-only runtime prints redacted FAIL lines, never driver text.
            for line in logs.splitlines():
                if re.fullmatch(r'FAIL: [a-zA-Z]+(?: SQLSTATE=[A-Z0-9]{5})?\..*', line):
                    print(line)
            raise
        finally:
            # Remove admin credential consumers before removing the one-time Secret.
            try:
                cluster.command(['delete', 'job', 'db-init-db', '--ignore-not-found', '--wait=true', '--timeout=60s'])
            finally:
                cluster.command(['delete', 'secret', 'db-admin-once', '--ignore-not-found'])
        print('PASS: DB-admin Job es atmeneti Secret eltavolitva.')
    elif args.action == 'deploy-litellm':
        preflight(v, cluster)
        # Do not run a migration against the database of a live serving deployment.
        current = cluster.get('deployment', 'litellm')
        if current and current.get('spec', {}).get('replicas', 0):
            fail('Meglevo LiteLLM deployment fut. Frissites elott a guide szerint allitsd le a fogyasztokat es skalazd 0-ra a LiteLLM-et.')
        if current:
            pods = json.loads(cluster.command(['get', 'pods', '-l', 'app.kubernetes.io/name=litellm', '-o', 'json']).stdout)['items']
            if any(p.get('status', {}).get('phase') not in ['Succeeded', 'Failed'] for p in pods):
                fail('A korabbi LiteLLM-pod meg leall. Vard meg a pod torleset a migracio elott.')
        cluster.run_job(manifests['db-check'])
        cluster.run_job(manifests['litellm-migrate'])
        cluster.apply(manifests['litellm-service'])
        cluster.apply(manifests['litellm-deployment'])
        cluster.command(['rollout', 'status', 'deployment/litellm', '--timeout=900s'], capture=False)
        result = cluster.exec_proxy('db.py', ['check-migrations'])
        print(result.stdout, end='')
    elif args.action == 'create-app-key': create_app_key(v, cluster)
    elif args.action == 'deploy-app':
        if not cluster.get('secret', 'streamlit-auth'): fail('Elobb create-app-key.')
        cluster.command(['rollout', 'status', 'deployment/litellm', '--timeout=60s'])
        cluster.apply(manifests['streamlit-service'])
        cluster.apply(manifests['streamlit-deployment'])
        cluster.command(['rollout', 'status', 'deployment/streamlit', '--timeout=600s'], capture=False)
    elif args.action == 'verify':
        cluster.command(['rollout', 'status', 'deployment/litellm', '--timeout=60s'])
        cluster.command(['rollout', 'status', 'deployment/streamlit', '--timeout=60s'])
        print(cluster.exec_proxy('db.py', ['check-migrations']).stdout, end='')
        code = "import urllib.request; o=urllib.request.build_opener(urllib.request.ProxyHandler({})); assert o.open('http://litellm:4000/health/readiness', timeout=10).status==200; assert o.open('http://127.0.0.1:8501/_stcore/health', timeout=10).read().strip()==b'ok'; print('PASS: app health es app -> LiteLLM Service readiness; modellhivas nelkul.')"
        cluster.command(['exec', 'deployment/streamlit', '--', 'python', '-c', code], capture=False)
    elif args.action == 'smoke':
        auth = json.loads((LOCAL / 'streamlit-auth.json').read_text())
        result = cluster.exec_proxy('admin.py', ['smoke'], input=json.dumps({'key': auth['LITELLM_API_KEY']}))
        data = json.loads(result.stdout)
        path = LOCAL / 'smoke-result.json'
        if path.exists(): path.unlink()
        private_write(path, data)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == 'verify-spend':
        result = json.loads((LOCAL / 'smoke-result.json').read_text())
        print(cluster.exec_proxy('db.py', ['verify-spend', '--call-id', result['litellm_call_id']]).stdout, end='')
    elif args.action == 'status': cluster.command(['get', 'pods,services,jobs', '-o', 'wide'], capture=False)


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, KeyError, ssl.SSLError):
        fail('Konfiguracios vagy helyi fajlhiba. Ellenorizd a settings.env es local/ fajlokat; titkos ertekeket nem irunk ki.')
