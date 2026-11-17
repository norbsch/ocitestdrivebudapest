#!/usr/bin/env python3
"""Create only missing workshop role/database. Keep existing passwords and data."""
import getpass
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def read_env(path):
    return dict(line.split('=', 1) for line in path.read_text().splitlines()
                if line and not line.startswith('#') and '=' in line)


def verify_application(psycopg, params):
    with psycopg.connect(**params, autocommit=True) as conn:
        if conn.info.server_version // 10000 != 16:
            raise SystemExit('Ez a workshop PostgreSQL 16 szerverhez keszult.')
        row = conn.execute("SELECT current_user, current_database(), has_schema_privilege(current_user, 'public', 'CREATE')").fetchone()
        if tuple(row) != ('litellm', 'litellm', True):
            raise SystemExit('Az alkalmazas DB-user/db neve vagy public schema CREATE joga nem megfelelo.')
    print('PASS: litellm adatbazis/felhasznalo, verify-full TLS es schema CREATE jog.')


def initialize(conn, password, sql):
    """Called with an admin connection in autocommit mode (CREATE DATABASE)."""
    if conn.info.server_version // 10000 != 16:
        raise SystemExit('Ez a workshop PostgreSQL 16 szerverhez keszult.')
    owner = conn.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='litellm'").fetchone()
    if owner is not None:
        if owner[0] != 'litellm':
            raise SystemExit('Meglevo litellm DB mas tulajdonossal; automatikusan nem modositjuk.')
        print('Meglevo litellm DB: nem irjuk felul, a jelszot nem allitjuk at.')
        return
    role = conn.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname='litellm'").fetchone()
    if role is None:
        enc = conn.info.encoding
        encrypted = conn.pgconn.encrypt_password(password.encode(enc), b'litellm', b'scram-sha-256').decode(enc)
        conn.execute(sql.SQL('CREATE ROLE litellm LOGIN PASSWORD {}').format(sql.Literal(encrypted)))
        print('A litellm szerepkor letrejott.')
    elif not role[0]:
        raise SystemExit('A meglevo litellm szerepkor nem LOGIN; automatikusan nem modositjuk.')
    else:
        print('Meglevo litellm szerepkor: jelszot nem allitunk at.')
    can_set = conn.execute("SELECT pg_has_role(current_user, 'litellm', 'SET')").fetchone()[0]
    had_membership = conn.execute("SELECT EXISTS (SELECT 1 FROM pg_auth_members WHERE roleid='litellm'::regrole AND member=current_user::regrole)").fetchone()[0]
    admin = conn.execute('SELECT current_user').fetchone()[0]
    if not can_set:
        conn.execute(sql.SQL('GRANT litellm TO {} WITH SET TRUE').format(sql.Identifier(admin)))
    try:
        conn.execute('CREATE DATABASE litellm OWNER litellm')
        print('A litellm adatbazis letrejott.')
    finally:
        if not can_set:
            if had_membership:
                conn.execute(sql.SQL('REVOKE SET OPTION FOR litellm FROM {}').format(sql.Identifier(admin)))
            else:
                conn.execute(sql.SQL('REVOKE litellm FROM {}').format(sql.Identifier(admin)))


def main():
    import psycopg
    from psycopg import sql
    v = read_env(ROOT / 'deployment.env')
    secret = read_env(ROOT / 'proxy/secrets/proxy.env')
    url = urlsplit(secret['DATABASE_URL'])
    if url.username != 'litellm' or unquote(url.path.lstrip('/')) != 'litellm':
        raise SystemExit('A konfiguracio csak litellm DB/user hasznalataval tamogatott.')
    if url.hostname != v['DB_HOST'] or url.port != int(v['DB_PORT']):
        raise SystemExit('A meglevo proxy.env DB celpontja elter a deployment.env-tol; egyeztesd a konfiguraciot.')
    params = dict(host=url.hostname, port=url.port, dbname='litellm', user='litellm',
                  password=unquote(url.password or ''), sslmode='verify-full',
                  sslrootcert=str(ROOT / 'proxy/secrets/postgres-ca.pem'), connect_timeout=10)
    try:
        verify_application(psycopg, params)
        return
    except psycopg.Error:
        print('Az alkalmazas DB-kapcsolata meg nem hasznalhato; egyszeri DB-admin ellenorzes kovetkezik.')
    admin_password = getpass.getpass('OCI PostgreSQL admin jelszava (' + v['DB_ADMIN'] + '): ')
    if not admin_password:
        raise SystemExit('Ures adminjelszo; inicializalas nem tortent.')
    admin_params = dict(params, dbname='postgres', user=v['DB_ADMIN'], password=admin_password)
    with psycopg.connect(**admin_params, autocommit=True) as conn:
        initialize(conn, params['password'], sql)
    verify_application(psycopg, params)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Driver/SQL text can contain credentials. Only a safe type/code is shown.
        code = getattr(exc, 'sqlstate', None)
        raise SystemExit('FAIL: DB elokeszites ' + type(exc).__name__ +
                         (' SQLSTATE=' + code if code else '') +
                         '. Ellenorizd a jelszavakat, TLS-t es a halozatot. Meglevo jelszo/adat nem lett felulirva.')
