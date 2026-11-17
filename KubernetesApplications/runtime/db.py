"""Explicit DB bootstrap and read-only checks; no infrastructure operations."""
import argparse
import json
import os
import re
from urllib.parse import quote, urlencode

CA = '/run/db-ca/postgres-ca.pem'


def params():
    return dict(host=os.environ['DB_HOST'], port=int(os.environ['DB_PORT']),
                dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'],
                password=os.environ['DB_PASSWORD'], sslmode='verify-full',
                sslrootcert=CA, connect_timeout=10)


def prisma_url():
    p = params()
    query = urlencode(dict(sslmode='require', sslaccept='strict', sslcert=CA,
                           connect_timeout=10, connection_limit=5, pool_timeout=15))
    return (f"postgresql://{quote(p['user'], safe='')}:{quote(p['password'], safe='')}"
            f"@{p['host']}:{p['port']}/{quote(p['dbname'], safe='')}?{query}")


def verify(driver):
    p = params()
    with driver.connect(**p, autocommit=True) as conn:
        if conn.info.server_version // 10000 != 16:
            raise ValueError('A csomag PostgreSQL 16 szerverhez keszult.')
        row = conn.execute("SELECT current_user, current_database(), has_schema_privilege(current_user, 'public', 'CREATE')").fetchone()
        if tuple(row) != (p['user'], p['dbname'], True):
            raise ValueError('Hibas DB-azonossag vagy hianyzo schema CREATE jog.')
        tls = conn.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()
        if not tls or tls[0] is not True:
            raise ValueError('TLS hianyzik.')
    print('PASS: alkalmazas DB-kapcsolat, PostgreSQL 16, verify-full TLS es schema CREATE jog.')


def initialize(driver, sql):
    """Only an explicit init-db Job receives the admin password."""
    p = params()
    admin_params = dict(p, dbname='postgres', user=os.environ['DB_ADMIN'],
                        password=os.environ['DB_ADMIN_PASSWORD'])
    with driver.connect(**admin_params, autocommit=True) as conn:
        if conn.info.server_version // 10000 != 16:
            raise ValueError('PostgreSQL 16 szukseges.')
        owner = conn.execute('SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s', (p['dbname'],)).fetchone()
        if owner is not None:
            if owner[0] != p['user']:
                raise ValueError('Meglevo DB mas tulajdonossal; nem modositjuk.')
        else:
            role = conn.execute('SELECT rolcanlogin FROM pg_roles WHERE rolname=%s', (p['user'],)).fetchone()
            if role is None:
                enc = conn.info.encoding
                hashed = conn.pgconn.encrypt_password(p['password'].encode(enc), p['user'].encode(enc), b'scram-sha-256').decode(enc)
                conn.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(p['user']), sql.Literal(hashed)))
            elif not role[0]:
                raise ValueError('Meglevo szerepkor nem LOGIN; nem modositjuk.')
            can_set = conn.execute("SELECT pg_has_role(current_user, %s, 'SET')", (p['user'],)).fetchone()[0]
            member = conn.execute('SELECT EXISTS (SELECT 1 FROM pg_auth_members WHERE roleid=%s::regrole AND member=current_user::regrole)', (p['user'],)).fetchone()[0]
            admin = conn.execute('SELECT current_user').fetchone()[0]
            if not can_set:
                conn.execute(sql.SQL('GRANT {} TO {} WITH SET TRUE').format(sql.Identifier(p['user']), sql.Identifier(admin)))
            try:
                conn.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(p['dbname']), sql.Identifier(p['user'])))
            finally:
                if not can_set:
                    text = 'REVOKE SET OPTION FOR {} FROM {}' if member else 'REVOKE {} FROM {}'
                    conn.execute(sql.SQL(text).format(sql.Identifier(p['user']), sql.Identifier(admin)))
    verify(driver)


def migrations(driver, call_id=None):
    verify(driver)
    with driver.connect(**params(), autocommit=True) as conn:
        applied, failed = conn.execute('SELECT count(*) FILTER (WHERE finished_at IS NOT NULL AND rolled_back_at IS NULL), count(*) FILTER (WHERE finished_at IS NULL AND rolled_back_at IS NULL) FROM "_prisma_migrations"').fetchone()
        if not applied or failed:
            raise ValueError('Hianyzo vagy befejezetlen migraciok.')
        print(f'PASS: {applied} sikeres migracio, nincs befejezetlen migracio.')
        if call_id:
            if not re.fullmatch(r'[a-zA-Z0-9-]{1,100}', call_id):
                raise ValueError('Ervenytelen call ID.')
            row = conn.execute('SELECT litellm_call_id, spend FROM "LiteLLM_SpendLogs" WHERE litellm_call_id=%s', (call_id,)).fetchone()
            if row is None or row[1] is None or row[1] <= 0:
                raise ValueError('Pozitiv spend sor meg nem lathato; csak ezt az olvasasi ellenorzest ismeteld kesobb.')
            print(json.dumps(dict(litellm_call_id=row[0], spend=str(row[1]))))
            print('PASS: a konkret modellhivas az adatbazisban megtalalhato.')


def safe_main():
    import psycopg
    from psycopg import sql
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['check-db', 'init-db', 'check-migrations', 'verify-spend'])
    parser.add_argument('--call-id')
    args = parser.parse_args()
    try:
        if args.action == 'init-db': initialize(psycopg, sql)
        elif args.action == 'check-db': verify(psycopg)
        else:
            if args.action == 'verify-spend' and not args.call_id:
                raise ValueError('Call ID szukseges.')
            migrations(psycopg, args.call_id)
    except Exception as exc:
        code = getattr(exc, 'sqlstate', None)
        raise SystemExit('FAIL: ' + type(exc).__name__ + (' SQLSTATE=' + code if code else '') + '. Ellenorizd a DB-cimet, jelszot, CA-t, halozatot es jogokat. Meglevo adatot/jelszot nem irunk felul.')


if __name__ == '__main__': safe_main()
