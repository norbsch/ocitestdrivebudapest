#!/usr/bin/env python3
"""Bounded HTTP readiness checks. Never issues inference requests or prints tokens."""
import argparse
from pathlib import Path
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def read_env(path):
    return dict(line.split('=', 1) for line in path.read_text().splitlines()
                if line and not line.startswith('#') and '=' in line)


def targets(kind):
    if kind == 'app':
        return [('http://127.0.0.1:80/_stcore/health', None, b'ok')]
    if kind == 'upstream':
        v = read_env(ROOT / 'app/.env')
        return [(v['LITELLM_BASE_URL'].rstrip('/') + '/health/liveliness', v['LITELLM_API_KEY'], None)]
    v = read_env(ROOT / 'proxy/secrets/proxy.env')
    return [('http://127.0.0.1:4000' + p, v['LITELLM_MASTER_KEY'], None)
            for p in ['/health/liveliness', '/health/readiness']]


def wait_for(kind, timeout=600):
    checks = targets(kind)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout
    tries = 0
    while time.monotonic() < deadline:
        try:
            for url, token, expected in checks:
                req = urllib.request.Request(url, headers={} if token is None else {'Authorization': 'Bearer ' + token})
                with opener.open(req, timeout=min(5, max(0.1, deadline - time.monotonic()))) as response:
                    body = response.read(2048)
                    if response.status != 200 or (expected is not None and body.strip() != expected):
                        raise ValueError('Not ready')
            print('PASS: ' + kind + ' HTTP health')
            return
        except (urllib.error.URLError, OSError, ValueError):
            tries += 1
            if tries % 6 == 1:
                print('Varakozas a szolgaltatasra: ' + kind, flush=True)
            time.sleep(min(5, max(0, deadline - time.monotonic())))
    raise SystemExit('FAIL: ' + kind + ' health timeout. Ellenorizd a VM szolgaltatasnaplojat es a halozatot; nincs automatikus modellhivas.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['litellm', 'app', 'upstream'])
    args = parser.parse_args()
    try:
        wait_for(args.kind, 120 if args.kind == 'upstream' else 600)
    except (OSError, KeyError, ValueError):
        raise SystemExit('FAIL: hianyzo vagy hibas konfiguracio. Titkos ertekeket nem irtunk ki.')


if __name__ == '__main__':
    main()
