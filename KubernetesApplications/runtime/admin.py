"""Executed explicitly inside the proxy pod. Never log input credentials."""
import argparse
from decimal import Decimal, InvalidOperation
import json
import os
import sys
import urllib.request


def call(path, token, body):
    request = urllib.request.Request('http://127.0.0.1:4000' + path,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
        data=json.dumps(body).encode())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=150) as response:
        return json.load(response), response.headers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['create-key', 'smoke'])
    args = parser.parse_args()
    if args.action == 'create-key':
        data, _ = call('/key/generate', os.environ['LITELLM_MASTER_KEY'], dict(
            models=['oci-cohere'], key_alias=os.environ['WORKSHOP_KEY_ALIAS'], max_budget=10, rpm_limit=10))
        print(json.dumps({'key': data['key']}))  # captured privately by the installer
    else:
        value = json.load(sys.stdin)
        data, headers = call('/v1/chat/completions', value['key'], dict(model='oci-cohere',
            messages=[{'role': 'user', 'content': 'Valaszolj egy szoval: mukodik?'}], max_tokens=32, stream=False))
        result = dict(answer=data['choices'][0]['message']['content'], usage=data.get('usage'),
                      cost_usd=headers.get('x-litellm-response-cost'), litellm_call_id=headers.get('x-litellm-call-id'))
        print(json.dumps(result, ensure_ascii=False))
        if not result['litellm_call_id'] or result['cost_usd'] is None or Decimal(result['cost_usd']) <= 0:
            raise SystemExit('FAIL: hianyzo call ID vagy pozitiv koltseg; ne ismeteld automatikusan a modellhivast.')


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, KeyError, InvalidOperation):
        raise SystemExit('FAIL: proxy/admin muvelet hibas vagy eredmenye bizonytalan. Nincs automatikus ujraprobalas; ellenorizd a proxyt.')
