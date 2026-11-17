#!/usr/bin/env python3
"""Download the public release to files on Linux or macOS, without a container engine."""
import argparse
import json
from pathlib import Path
import re

from workshop import fail, run

ROOT = Path(__file__).resolve().parents[1]


def pull_images():
    release = {}
    for line in (ROOT / 'images.env').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or key in release:
            fail('Hibas vagy ismetelt images.env sor.')
        release[key] = value
    if release.get('IMAGE_PULL_AUTH') != 'public':
        fail('Ez a letolto a nyilvanos workshop-kiadashoz keszult.')
    refs = [release.get(key, '') for key in ['APP_IMAGE', 'PROXY_IMAGE']]
    for ref in refs:
        if not re.fullmatch(r'[a-zA-Z0-9.-]+(?::[0-9]+)?/[a-zA-Z0-9._/-]+@sha256:[a-f0-9]{64}', ref):
            fail('Az images.env fajlban ket vegleges, digestes kepcim szukseges.')
    # Explicit platform also works on macOS/ARM clients. Directory transport keeps
    # the released manifest intact; --preserve-digests rejects any conversion.
    skopeo = ['skopeo', '--override-os', 'linux', '--override-arch', 'amd64']
    for name, ref in zip(['streamlit', 'litellm'], refs):
        digest = ref.rsplit('@', 1)[1]
        destination = ROOT / 'local' / 'images' / name / digest.split(':', 1)[1]
        destination.mkdir(mode=0o700, parents=True, exist_ok=True)
        target = 'dir:' + str(destination.resolve())
        run(skopeo + ['copy', '--src-no-creds', '--src-tls-verify=true', '--preserve-digests',
                      'docker://' + ref, target], capture=False)
        result = json.loads(run(skopeo + ['inspect', target]).stdout)
        if result.get('Os') != 'linux' or result.get('Architecture') != 'amd64':
            fail('A letoltott kep nem Linux/AMD64.')
        if result.get('Digest') != digest:
            fail('A letoltott kep digestje nem egyezik a kiadassal.')
        print('PASS: helyben letoltve, Linux/AMD64, digest ellenorizve: ' + ref)
    print('PASS: mindket kep a local/images konyvtarban van; clustertelepites meg nem tortent.')


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        pull_images()
    except (OSError, ValueError, KeyError, IndexError):
        fail('Hibas kiadasi fajl, Skopeo valasz vagy hianyzo eszkoz. Ellenorizd az images.env fajlt es a skopeo --version kimenetet.')
