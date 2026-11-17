"""Offline tests: no OCI, Kubernetes, container build or real DB operation."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import manifests
import workshop
spec = importlib.util.spec_from_file_location('runtime_db', ROOT / 'runtime/db.py')
db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db)


def values():
    v = dict(line.split('=', 1) for line in (ROOT / 'templates/settings.env.example').read_text().splitlines() if line and not line.startswith('#'))
    v.update(KUBE_CONTEXT='test-context', OCIR_NAMESPACE='testnamespace', OCIR_USERNAME='Default/test@example.com',
        DB_HOST='primary.example.test', DB_ADMIN='pgadmin', APP_PUBLIC_HOST='lb.example.test', OCI_COMPARTMENT_ID='ocid1.compartment.test',
        OCI_USER='ocid1.user.test', OCI_TENANCY='ocid1.tenancy.test', OCI_FINGERPRINT=':'.join(['ab'] * 16))
    return v


class ManifestTests(unittest.TestCase):
    def setUp(self): self.all = manifests.all_manifests(values())

    def test_only_streamlit_nodeport_no_ingress_or_loadbalancer(self):
        services = [x for x in self.all.values() if x['kind'] == 'Service']
        self.assertEqual({x['spec']['type'] for x in services}, {'ClusterIP', 'NodePort'})
        self.assertEqual(self.all['streamlit-service']['spec']['externalTrafficPolicy'], 'Cluster')
        self.assertEqual(self.all['streamlit-service']['spec']['ports'][0]['nodePort'], 30080)
        self.assertEqual(self.all['litellm-service']['spec']['ports'][0]['port'], 4000)

    def test_one_replica_and_recreate(self):
        for name in ['streamlit-deployment', 'litellm-deployment']:
            self.assertEqual(self.all[name]['spec']['replicas'], 1)
            self.assertEqual(self.all[name]['spec']['strategy']['type'], 'Recreate')

    def test_pods_nonroot_amd64_without_kube_token(self):
        for obj in self.all.values():
            if obj['kind'] not in ['Job', 'Deployment']: continue
            pod = obj['spec']['template']['spec']
            self.assertEqual(pod['nodeSelector']['kubernetes.io/arch'], 'amd64')
            self.assertEqual(pod['securityContext']['runAsUser'], 10001)
            self.assertFalse(pod['automountServiceAccountToken'])
            self.assertEqual(pod['imagePullSecrets'], [{'name': 'ocir-pull'}])
            self.assertFalse(pod['containers'][0]['securityContext']['allowPrivilegeEscalation'])

    def test_admin_secret_only_in_explicit_init_job(self):
        for name, obj in self.all.items():
            self.assertEqual('db-admin-once' in json.dumps(obj), name == 'db-init')

    def test_application_never_receives_proxy_db_or_oci_secrets(self):
        text = json.dumps(self.all['streamlit-deployment'])
        for forbidden in ['litellm-auth', 'oci-api-key', 'DB_PASSWORD', 'db-admin-once']:
            self.assertNotIn(forbidden, text)
        self.assertIn('streamlit-auth', text)
        self.assertIn('http://litellm:4000', text)

    def test_liveness_is_not_model_health_and_jobs_do_not_retry(self):
        container = self.all['litellm-deployment']['spec']['template']['spec']['containers'][0]
        self.assertEqual(container['livenessProbe']['httpGet']['path'], '/health/liveliness')
        self.assertEqual(container['readinessProbe']['httpGet']['path'], '/health/readiness')
        for obj in self.all.values():
            if obj['kind'] == 'Job':
                self.assertEqual(obj['spec']['backoffLimit'], 0)
                self.assertEqual(obj['spec']['template']['spec']['restartPolicy'], 'Never')

    def test_secret_volume_readable_by_nonroot_group(self):
        volumes = self.all['litellm-deployment']['spec']['template']['spec']['volumes']
        self.assertEqual(next(v['secret']['defaultMode'] for v in volumes if v['name'] == 'oci-key'), 0o440)

    def test_all_namespaces_images_and_selectors_match(self):
        for obj in self.all.values():
            if obj['kind'] != 'Namespace': self.assertEqual(obj['metadata']['namespace'], values()['NAMESPACE'])
            if obj['kind'] == 'Deployment':
                self.assertEqual(obj['spec']['selector']['matchLabels'], obj['spec']['template']['metadata']['labels'])
        self.assertEqual(self.all['streamlit-service']['spec']['selector'], self.all['streamlit-deployment']['spec']['selector']['matchLabels'])
        self.assertIn('testnamespace/oci-ai-k8s-streamlit:workshop-v1', json.dumps(self.all))


class DBTests(unittest.TestCase):
    def test_strict_tls_url_and_password_escaping(self):
        password = 'a@:/?&% +$test'
        with patch.dict(os.environ, {'DB_HOST': 'primary.example.test', 'DB_PORT': '5432',
            'DB_NAME': 'custom_db', 'DB_USER': 'custom_user', 'DB_PASSWORD': password}):
            url = urlsplit(db.prisma_url())
            self.assertEqual(unquote(url.password), password)
            self.assertEqual(url.username, 'custom_user')
            self.assertEqual(url.path, '/custom_db')
            self.assertEqual(parse_qs(url.query)['sslaccept'], ['strict'])
            self.assertEqual(parse_qs(url.query)['sslcert'], [db.CA])
            self.assertEqual(db.params()['sslmode'], 'verify-full')

    def test_application_check_only_selects_and_rejects_no_tls(self):
        for enabled in [True, False]:
            conn = MagicMock()
            conn.__enter__.return_value = conn
            conn.info.server_version = 160013
            conn.execute.return_value.fetchone.side_effect = [('custom_user', 'custom_db', True), (enabled,)]
            driver = SimpleNamespace(connect=MagicMock(return_value=conn))
            with patch.object(db, 'params', return_value={'user': 'custom_user', 'dbname': 'custom_db'}), redirect_stdout(io.StringIO()):
                if enabled: db.verify(driver)
                else:
                    with self.assertRaises(ValueError): db.verify(driver)
            self.assertTrue(all(call.args[0].startswith('SELECT') for call in conn.execute.call_args_list))

    def test_dynamic_role_identifiers_and_cleanup_on_create_failure(self):
        class TextSQL(str):
            def format(self, *items): return TextSQL(str(self).format(*items))
        sql = SimpleNamespace(SQL=TextSQL, Identifier=lambda x: '"' + x + '"', Literal=lambda x: "'" + x + "'")
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.info.server_version, conn.info.encoding = 160013, 'utf-8'
        queries = []
        def execute(query, params=None):
            query = str(query)
            queries.append(query)
            if query.startswith('CREATE DATABASE'): raise RuntimeError('simulated failure')
            row = None
            if 'rolcanlogin' in query: row = (True,)
            elif 'pg_has_role' in query: row = (False,)
            elif 'pg_auth_members' in query: row = (True,)
            elif query == 'SELECT current_user': row = ('pgadmin',)
            return SimpleNamespace(fetchone=lambda: row)
        conn.execute.side_effect = execute
        driver = SimpleNamespace(connect=MagicMock(return_value=conn))
        p = dict(user='custom_user', dbname='custom_db', password='not-printed')
        with patch.object(db, 'params', return_value=p), patch.dict(os.environ, DB_ADMIN='pgadmin', DB_ADMIN_PASSWORD='admin-not-printed'), self.assertRaises(RuntimeError):
            db.initialize(driver, sql)
        self.assertIn('CREATE DATABASE "custom_db" OWNER "custom_user"', queries)
        self.assertEqual(queries[-1], 'REVOKE SET OPTION FOR "custom_user" FROM "pgadmin"')
        self.assertFalse(any('PASSWORD' in q for q in queries))


class InstallerTests(unittest.TestCase):
    def test_private_state_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'credentials.json'
            workshop.private_write(path, {'password': 'test-only'})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError): workshop.private_write(path, {'password': 'other'})
            self.assertEqual(json.loads(path.read_text())['password'], 'test-only')

    def test_every_cluster_command_pins_context_and_namespace(self):
        with patch.object(workshop, 'run', return_value=SimpleNamespace(stdout='')) as run:
            workshop.Cluster(values()).command(['get', 'pods'])
            self.assertEqual(run.call_args.args[0][:5], ['kubectl', '--context', 'test-context', '-n', 'oci-ai-k8s'])

    def test_secret_conflict_not_overwritten(self):
        cluster = workshop.Cluster(values())
        with patch.object(cluster, 'get', return_value={'data': {'DB_PASSWORD': 'old'}}), patch.object(cluster, 'apply') as apply, self.assertRaises(SystemExit):
            cluster.secret('litellm-auth', {'DB_PASSWORD': 'new'})
        apply.assert_not_called()

    def test_subprocess_failure_does_not_print_secret_output(self):
        output = io.StringIO()
        with patch.object(workshop.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='secret-token', stderr='secret-password')), redirect_stdout(output), self.assertRaises(SystemExit) as exc:
            workshop.run(['kubectl', 'get', 'pods'])
        self.assertNotIn('secret-token', str(exc.exception) + output.getvalue())
        self.assertNotIn('secret-password', str(exc.exception) + output.getvalue())

    def test_namespace_not_owned_is_never_adopted(self):
        cluster = workshop.Cluster(values())
        with patch.object(cluster, 'get', return_value={'metadata': {'labels': {}}}), patch.object(cluster, 'apply') as apply, self.assertRaises(SystemExit):
            cluster.ensure_namespace()
        apply.assert_not_called()

    def test_uncertain_key_creation_is_not_retried(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(workshop, 'LOCAL', Path(folder)):
            Path(folder, 'key-create-attempt.json').write_text('{}')
            cluster = MagicMock()
            with self.assertRaises(SystemExit): workshop.create_app_key(values(), cluster)
            cluster.exec_proxy.assert_not_called()

    def test_same_saved_key_reused_without_remote_key_generation(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(workshop, 'LOCAL', Path(folder)), redirect_stdout(io.StringIO()):
            data = {'LITELLM_API_KEY': 'sk-test', 'STREAMLIT_SERVER_COOKIE_SECRET': 'cookie-test'}
            Path(folder, 'streamlit-auth.json').write_text(json.dumps(data))
            cluster = MagicMock()
            workshop.create_app_key(values(), cluster)
            cluster.exec_proxy.assert_not_called()
            cluster.secret.assert_called_once_with('streamlit-auth', data)


if __name__ == '__main__': unittest.main()
