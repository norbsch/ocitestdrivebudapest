#!/usr/bin/env python3
"""Instructor image publishing on a Linux/AMD64 VM with Docker and adequate disk."""
import argparse
import getpass
import json
import os
import platform
import re
import shutil
import tempfile
from pathlib import Path

from publish import ROOT, load_settings, refs, write_release, verify_remote
from workshop import fail, run


def check():
    if platform.system() != 'Linux' or platform.machine() not in ['x86_64', 'amd64']:
        fail('Linux/AMD64 build VM szukseges.')
    for tool in ['docker', 'skopeo']:
        if not shutil.which(tool): fail('Hianyzo eszkoz: '+tool)
    data = json.loads(run(['docker', 'info', '--format', '{{json .}}']).stdout)
    if data.get('OSType') != 'linux': fail('Linux Docker engine szukseges.')
    print('PASS: Docker build VM; Docker tarhely: '+data['DockerRootDir'])


def build(v):
    for name, reference in refs(v).items():
        folder = 'app' if name == 'APP' else 'proxy'
        print('Build: '+reference, flush=True)
        run(['docker', 'build', '--platform', 'linux/amd64', '-f', str(ROOT/folder/'Dockerfile'),
             '-t', reference, str(ROOT)], capture=False)
        metadata = json.loads(run(['docker', 'image', 'inspect', reference]).stdout)[0]
        if (metadata.get('Os'),metadata.get('Architecture')) != ('linux','amd64'):
            fail('Hibas kepplatform: '+reference)
        code = ('import streamlit; from client import complete; print("PASS: Streamlit imports")' if name == 'APP' else
                'import litellm, psycopg; from prisma import Prisma; import sys; sys.path.insert(0,"/opt/workshop/runtime"); import db; print("PASS: LiteLLM/Prisma/psycopg imports")')
        run(['docker','run','--rm','--network=none','--entrypoint','python',reference,'-c',code],capture=False)
    print('PASS: mindket kep elkeszult es az importproba sikeres.')


def push(v):
    references=refs(v)
    for reference in references.values():
        meta=json.loads(run(['docker','image','inspect',reference]).stdout)[0]
        if (meta.get('Os'),meta.get('Architecture')) != ('linux','amd64'): fail('Hibas kepplatform.')
    token=getpass.getpass('Sajat OCI Auth Token az OCIR pushhoz: ')
    if not token: fail('Ures OCIR token.')
    with tempfile.TemporaryDirectory(prefix='oci-ai-publish-') as folder:
        config=Path(folder)/'config.json'
        config.write_text('{"auths":{}}');config.chmod(0o600)
        prefix=['docker','--config',folder]
        run(prefix+['login',v['REGISTRY'],'--username',v['OCIR_NAMESPACE']+'/'+v['OCIR_USERNAME'],'--password-stdin'],input=token+'\n')
        release={'IMAGE_PULL_AUTH':v['IMAGE_PULL_AUTH']}
        for name,reference in references.items():
            run(prefix+['push',reference],capture=False)
            meta=json.loads(run(['docker','image','inspect',reference]).stdout)[0]
            repository=reference.rsplit(':',1)[0]
            candidates=[d for d in meta.get('RepoDigests',[]) if re.fullmatch(re.escape(repository)+r'@sha256:[a-f0-9]{64}',d)]
            if len(candidates)!=1:fail('Nem egyertelmu registry digest.')
            release[name+'_IMAGE']=candidates[0]
            verify_remote(candidates[0],v['IMAGE_PULL_AUTH'],config)
        write_release(release)
    print('PASS: mindket kep az OCIR-ben; images.env es SHA256SUMS frissitve.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['check','build','push','build-push'])
    action=parser.parse_args().action
    check()
    if action=='check':return
    v=load_settings()
    if action in ['build','build-push']:build(v)
    if action in ['push','build-push']:push(v)


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError):fail('VM publish konfiguracios vagy Docker metadata hiba.')
