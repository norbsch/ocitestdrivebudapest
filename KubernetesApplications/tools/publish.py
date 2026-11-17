#!/usr/bin/env python3
"""Instructor-only Cloud Shell Podman build/push in an isolated /tmp store."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import platform

from workshop import fail, run

ROOT = Path(__file__).resolve().parents[1]


def load_settings():
    path = ROOT / 'publish.env'
    if not path.is_file(): fail('Masold le a templates/publish.env.example fajlt publish.env neven es toltsd ki.')
    result = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith('#'):
            key, sep, value = line.partition('=')
            if not sep or key != key.strip() or key in result: fail('Hibas/ismetelt publish.env sor.')
            result[key] = value.strip()
    for key in ['REGISTRY', 'OCIR_NAMESPACE', 'OCIR_USERNAME', 'APP_REPOSITORY', 'PROXY_REPOSITORY', 'IMAGE_TAG', 'IMAGE_PULL_AUTH']:
        if not result.get(key) or 'REPLACE' in result[key]: fail('Toltsd ki a publish.env mezot: ' + key)
    for key in ['REGISTRY', 'OCIR_NAMESPACE', 'APP_REPOSITORY', 'PROXY_REPOSITORY']:
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', result[key]): fail('Ervenytelen publikacios mező: ' + key)
    if not re.fullmatch(r'[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}', result['IMAGE_TAG']) or result['IMAGE_TAG'] == 'latest':
        fail('Egyedi verziozott kep-tag kell, peldaul workshop-v1; ne latest legyen.')
    if result['IMAGE_PULL_AUTH'] not in ['public', 'private']: fail('IMAGE_PULL_AUTH: public vagy private.')
    return result


def refs(v):
    prefix = v['REGISTRY'] + '/' + v['OCIR_NAMESPACE'] + '/'
    return {name: prefix + v[name + '_REPOSITORY'] + ':' + v['IMAGE_TAG'] for name in ['APP', 'PROXY']}


class Builder:
    def __init__(self):
        raw = os.environ.get('WORKSHOP_BUILD_ROOT', '')
        path = Path(raw)
        if not raw or not path.is_absolute() or path.parent != Path('/tmp') or not path.name.startswith('oci-ai-k8s.'):
            fail('Exportald a mktemp altal keszitett /tmp/oci-ai-k8s.* WORKSHOP_BUILD_ROOT konyvtarat a PUBLISH guide szerint.')
        if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
            fail('A build konyvtar sajat tulajdonu, nem symlink es 0700 jogosultsagu legyen.')
        self.root = path
        for name in ['storage', 'run', 'tmp']:
            child = path / name
            if child.is_symlink(): fail('Symlink nem lehet a build tarhelyben.')
            child.mkdir(mode=0o700, exist_ok=True)
        self.prefix = ['podman', '--root', str(path/'storage'), '--runroot', str(path/'run'),
                       '--storage-driver=overlay', '--storage-opt=overlay.mount_program=/usr/bin/fuse-overlayfs']
        self.env = dict(os.environ, TMPDIR=str(path/'tmp'))

    def call(self, *args, **kwargs):
        return run(self.prefix + list(args), env=self.env, **kwargs)

    def check(self):
        if platform.system() != 'Linux' or platform.machine() not in ['x86_64', 'amd64']:
            fail('A buildhez x86_64 Linux Cloud Shell kell.')
        for command in ['podman', 'skopeo', '/usr/bin/fuse-overlayfs']:
            if not shutil.which(command): fail('Hianyzo Cloud Shell eszkoz: ' + command)
        actual = self.call('info', '--format', '{{.Store.GraphRoot}}').stdout.strip()
        if actual != str(self.root/'storage'): fail('Nem az elkulonitett build tarhely aktiv.')
        free = shutil.disk_usage(self.root).free / 1024**3
        print(f'PASS: elkulonitett AMD64 Podman tarhely: {actual}; szabad: {free:.1f} GiB.')


def build_one(builder, name, reference):
    dockerfile = 'app/Dockerfile' if name == 'APP' else 'proxy/Dockerfile'
    print('Build: ' + reference, flush=True)
    builder.call('build', '--platform', 'linux/amd64', '--layers=false', '--force-rm',
                 '-f', str(ROOT/dockerfile), '-t', reference, str(ROOT), capture=False)
    data = json.loads(builder.call('image', 'inspect', reference).stdout)[0]
    if (data.get('Os'), data.get('Architecture')) != ('linux', 'amd64'):
        fail('A kep nem linux/amd64: ' + reference)
    check = ('import streamlit; from client import complete; print("PASS: Streamlit image import")'
             if name == 'APP' else
             'import litellm, psycopg; from prisma import Prisma; import sys; sys.path.insert(0,"/opt/workshop/runtime"); import db; print("PASS: LiteLLM/Prisma/psycopg image import")')
    builder.call('run', '--rm', '--network=none', '--entrypoint', 'python', reference, '-c', check, capture=False)


def digest_reference(reference, digest):
    digest = digest.strip()
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest): fail('Hibas push digest; az images.env nem frissult.')
    return reference.rsplit(':', 1)[0] + '@' + digest


def verify_remote(reference, mode, auth):
    command = ['skopeo', 'inspect', '--tls-verify=true']
    command += ['--no-creds'] if mode == 'public' else ['--authfile', str(auth)]
    result = run(command + ['docker://' + reference], check=False)
    if result.returncode:
        fail('A registry ellenorzes sikertelen. Public kiadasnal anonim olvasas kell; az images.env nem frissult.')
    data = json.loads(result.stdout)
    if (data.get('Os'), data.get('Architecture'), data.get('Digest')) != ('linux', 'amd64', reference.split('@', 1)[1]):
        fail('Eltero registry digest vagy architektura; az images.env nem frissult.')


def write_release(release):
    text = '# Kesz OCIR kiadas, ellenorzott registry digestekkel. Nem tartalmaz hitelesitot.\n'
    text += ''.join(key + '=' + release[key] + '\n' for key in ['APP_IMAGE', 'PROXY_IMAGE', 'IMAGE_PULL_AUTH'])
    dest = ROOT / 'images.env'
    temp = dest.with_suffix('.env.new')
    temp.write_text(text)
    temp.chmod(0o644)
    os.replace(temp, dest)
    checksum = ROOT / 'SHA256SUMS'
    if checksum.is_file():
        lines = [line for line in checksum.read_text().splitlines() if not line.endswith('  images.env')]
        lines.append(hashlib.sha256(dest.read_bytes()).hexdigest() + '  images.env')
        checksum.write_text('\n'.join(sorted(lines, key=lambda line: line.split('  ', 1)[1])) + '\n')


def build_push(v, builder):
    local = ROOT/'local'
    local.mkdir(mode=0o700, exist_ok=True)
    auth = local/'publisher-auth.json'
    # Keep registry login separate from every other Cloud Shell tool's auth store.
    if auth.is_symlink(): fail('A publisher auth fajl nem lehet symlink.')
    fd = os.open(auth, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream: stream.write('{"auths":{}}')
    auth.chmod(0o600)
    token = getpass.getpass('Sajat OCI Auth Token az OCIR pushhoz: ')
    if not token: fail('Ures OCIR token.')
    try:
        builder.call('login', '--authfile', str(auth), '--username', v['OCIR_NAMESPACE']+'/'+v['OCIR_USERNAME'],
                     '--password-stdin', v['REGISTRY'], input=token+'\n')
        release = {'IMAGE_PULL_AUTH': v['IMAGE_PULL_AUTH']}
        for name, reference in refs(v).items():
            build_one(builder, name, reference)
            digestfile = builder.root/(name.lower()+'-digest.txt')
            if digestfile.is_symlink(): fail('Symlink digest fajl.')
            digestfile.unlink(missing_ok=True)
            builder.call('push', '--authfile', str(auth), '--tls-verify=true', '--digestfile', str(digestfile),
                         reference, 'docker://'+reference, capture=False)
            release[name+'_IMAGE'] = digest_reference(reference, digestfile.read_text())
            verify_remote(release[name+'_IMAGE'], v['IMAGE_PULL_AUTH'], auth)
            print('PASS: feltoltve es registrybol ellenorizve: '+release[name+'_IMAGE'], flush=True)
            # Only this explicitly selected temporary store is pruned, after a verified push.
            builder.call('image', 'prune', '-a', '-f', capture=False)
        write_release(release)
        print('PASS: mindket kep az OCIR-ben; images.env es SHA256SUMS frissitve.')
    finally:
        auth.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'build-push'])
    args = parser.parse_args()
    builder = Builder()
    builder.check()
    if args.action == 'build-push': build_push(load_settings(), builder)


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, KeyError): fail('Publish-konfiguracio vagy Podman metadata hiba. Titkos adatot nem irunk ki.')
