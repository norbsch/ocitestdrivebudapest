"""Build a strict TLS Prisma URL at runtime, then replace this process."""
import os
from pathlib import Path
import sys
from db import prisma_url, safe_main


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'serve'
    if action in ['check-db', 'init-db', 'check-migrations', 'verify-spend']:
        safe_main()
        return
    if action not in ['serve', 'migrate']:
        raise SystemExit('Ismeretlen inditasi mod.')
    import yaml
    config = yaml.safe_load(Path('/etc/workshop/config.yaml').read_text())
    config.setdefault('general_settings', {})['disable_prisma_schema_update'] = action != 'migrate'
    dest = Path('/tmp/litellm-config.yaml')
    dest.write_text(yaml.safe_dump(config))
    dest.chmod(0o600)
    os.environ['DATABASE_URL'] = prisma_url()
    os.environ['DISABLE_SCHEMA_UPDATE'] = 'false' if action == 'migrate' else 'true'
    command = ['litellm', '--config', str(dest), '--host', '0.0.0.0', '--port', '4000', '--num_workers', '1']
    if action == 'migrate': command.append('--skip_server_startup')
    os.execvp(command[0], command)


if __name__ == '__main__': main()
