"""Offline tests: no OCI, Kubernetes, container build or real DB operation."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
import re
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
import publish
import publish_vm
import pull_images
import verify_package
spec = importlib.util.spec_from_file_location('runtime_db', ROOT / 'runtime/db.py')
db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db)


def values():
    v = dict(line.split('=', 1) for line in (ROOT / 'templates/settings.env.example').read_text().splitlines() if line and not line.startswith('#'))
    v.update(KUBE_CONTEXT='test-context', IMAGE_PULL_AUTH='private', APP_IMAGE='fra.ocir.io/testnamespace/oci-ai-k8s-streamlit:workshop-v1', PROXY_IMAGE='fra.ocir.io/testnamespace/oci-ai-k8s-litellm:workshop-v1', OCIR_LOGIN='testnamespace/Default/test@example.com',
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

    def test_public_images_have_no_pull_secret_on_any_pod(self):
        config = values()
        config['IMAGE_PULL_AUTH'] = 'public'
        for obj in manifests.all_manifests(config).values():
            if obj['kind'] in ['Job', 'Deployment']:
                self.assertNotIn('imagePullSecrets', obj['spec']['template']['spec'])

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


class PublishingTests(unittest.TestCase):
    def config(self):
        return dict(REGISTRY='fra.ocir.io', OCIR_NAMESPACE='publisher', OCIR_USERNAME='Default/instructor',
            APP_REPOSITORY='workshop-app', PROXY_REPOSITORY='workshop-proxy', IMAGE_TAG='v1', IMAGE_PULL_AUTH='public')

    def test_public_participant_never_needs_registry_token(self):
        config = values()
        config['IMAGE_PULL_AUTH'] = 'public'
        with patch.object(workshop.getpass, 'getpass') as prompt, patch.object(workshop, 'private_write') as write, redirect_stdout(io.StringIO()):
            workshop.registry_login(config)
        prompt.assert_not_called()
        write.assert_not_called()

    def test_public_prepare_does_not_require_builder_auth_file(self):
        config = values()
        config['IMAGE_PULL_AUTH'] = 'public'
        public_bytes = b'test-public-der'
        config['OCI_FINGERPRINT'] = ':'.join(re.findall('..', workshop.hashlib.md5(public_bytes).hexdigest()))
        with tempfile.TemporaryDirectory() as folder, patch.object(workshop, 'ROOT', Path(folder)), patch.object(workshop, 'LOCAL', Path(folder)/'local'), patch.object(workshop, 'preflight'), patch.object(workshop.ssl, 'create_default_context'), patch.object(workshop.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=public_bytes)), patch.object(workshop.getpass, 'getpass', side_effect=['test-db-password', 'test-db-password']), redirect_stdout(io.StringIO()):
            local = Path(folder)/'local'
            local.mkdir()
            (local/'oci-api-key.pem').write_text('dummy-key')
            (local/'postgres-ca.pem').write_text('dummy-ca')
            (Path(folder)/'proxy').mkdir()
            (Path(folder)/'proxy/config.yaml').write_text('model_list: []')
            cluster = MagicMock()
            cluster.get.return_value = None
            workshop.prepare(config, cluster)
            self.assertEqual([c.args[0] for c in cluster.secret.call_args_list], ['litellm-auth', 'oci-api-key'])
            self.assertFalse((local/'registry-auth.json').exists())

    def test_public_release_requires_anonymous_registry_access(self):
        ref = 'fra.ocir.io/publisher/app@sha256:'+'a'*64
        with patch.object(publish, 'run', return_value=SimpleNamespace(returncode=1)) as run:
            with self.assertRaises(SystemExit): publish.verify_remote(ref, 'public', Path('/unused/auth.json'))
        self.assertIn('--no-creds', run.call_args.args[0])
        self.assertNotIn('--authfile', run.call_args.args[0])

    def test_build_explicitly_targets_amd64_and_isolates_imports(self):
        builder = MagicMock()
        builder.call.return_value.stdout = json.dumps([{'Os':'linux', 'Architecture':'amd64'}])
        with redirect_stdout(io.StringIO()): publish.build_one(builder, 'APP', 'registry/app:v1')
        build = builder.call.call_args_list[0].args
        self.assertEqual(build[build.index('--platform')+1], 'linux/amd64')
        self.assertIn('--layers=false', build)
        check = builder.call.call_args_list[-1].args
        self.assertEqual(check[0], 'run')
        self.assertIn('--network=none', check)

    def test_digest_validation_and_repository_binding(self):
        ref = 'fra.ocir.io/publisher/app:v1'
        self.assertEqual(publish.digest_reference(ref, 'sha256:'+'a'*64), ref.rsplit(':',1)[0]+'@sha256:'+'a'*64)
        with self.assertRaises(SystemExit): publish.digest_reference(ref, 'invalid')
        with patch.object(publish, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps({'Os':'linux','Architecture':'arm64','Digest':'sha256:'+'a'*64}))):
            with self.assertRaises(SystemExit): publish.verify_remote(ref.rsplit(':',1)[0]+'@sha256:'+'a'*64, 'public', Path('auth'))

    def test_store_rejects_home_and_symlink_and_scopes_every_podman_call(self):
        with patch.dict(publish.os.environ, {'WORKSHOP_BUILD_ROOT':'/home/user/.local/share/containers/storage'}):
            with self.assertRaises(SystemExit): publish.Builder()
        with tempfile.TemporaryDirectory(prefix='oci-ai-k8s.', dir='/tmp') as folder:
            folder = str(Path(folder).absolute())
            with patch.dict(publish.os.environ, {'WORKSHOP_BUILD_ROOT':folder}), patch.object(publish, 'run') as run:
                builder = publish.Builder()
                builder.call('image', 'prune', '-a', '-f')
                command = run.call_args.args[0]
                self.assertEqual(command[command.index('--root')+1], folder+'/storage')
                self.assertIn('--storage-opt=overlay.mount_program=/usr/bin/fuse-overlayfs', command)
                self.assertEqual(run.call_args.kwargs['env']['TMPDIR'], folder+'/tmp')
            link = Path(folder)/'link'
            link.symlink_to(folder)
            with patch.dict(publish.os.environ, {'WORKSHOP_BUILD_ROOT':str(link)}):
                with self.assertRaises(SystemExit): publish.Builder()

    def test_failed_second_build_preserves_release_and_cleans_token(self):
        token = 'do-not-print-this-token'
        with tempfile.TemporaryDirectory() as folder, patch.object(publish, 'ROOT', Path(folder)), patch.object(publish.getpass, 'getpass', return_value=token), patch.object(publish, 'build_one') as build, patch.object(publish, 'verify_remote'), redirect_stdout(io.StringIO()):
            root = Path(folder)
            (root/'images.env').write_text('old-release')
            builder = MagicMock()
            builder.root = root
            events = []
            def execute(*args, **kwargs):
                events.append(args[0])
                if args[0] == 'push': Path(args[args.index('--digestfile')+1]).write_text('sha256:'+'a'*64)
            builder.call.side_effect = execute
            def building(_, name, reference):
                events.append('build-'+name)
                if name == 'PROXY': raise SystemExit('simulated second build failure')
            build.side_effect = building
            with self.assertRaises(SystemExit): publish.build_push(self.config(), builder)
            self.assertEqual((root/'images.env').read_text(), 'old-release')
            self.assertEqual(events, ['login','build-APP','push','image','build-PROXY'])
            self.assertFalse((root/'local/publisher-auth.json').exists())
            login = builder.call.call_args_list[0]
            self.assertNotIn(token, ' '.join(login.args))
            self.assertEqual(login.kwargs['input'], token+'\n')

    def test_release_uses_publisher_refs_without_touching_participant_db_settings(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(workshop, 'ROOT', Path(folder)), redirect_stdout(io.StringIO()):
            path = Path(folder)
            config = (ROOT/'templates/settings.env.example').read_text()
            (path/'settings.env').write_text(config.replace('DB_NAME=litellm_k8s', 'DB_NAME=my_database'))
            release = 'APP_IMAGE=fra.ocir.io/publisher/app@sha256:'+'a'*64+'\nPROXY_IMAGE=fra.ocir.io/publisher/proxy@sha256:'+'b'*64+'\nIMAGE_PULL_AUTH=public\n'
            (path/'images.env').write_text(release)
            workshop.use_published_images()
            result = (path/'settings.env').read_text()
            self.assertIn('DB_NAME=my_database', result)
            self.assertIn('IMAGE_PULL_AUTH=public', result)
            self.assertIn('APP_IMAGE=fra.ocir.io/publisher/app@sha256:', result)
            self.assertEqual((path/'settings.env').stat().st_mode & 0o777, 0o600)


class VmPublishingTests(unittest.TestCase):
    def test_wrong_architecture_stops_build_before_import_or_next_image(self):
        with patch.object(publish_vm, 'refs', return_value={'APP':'registry/app:v1','PROXY':'registry/proxy:v1'}), patch.object(publish_vm, 'run') as run, redirect_stdout(io.StringIO()):
            run.return_value.stdout=json.dumps([{'Os':'linux','Architecture':'arm64'}])
            with self.assertRaises(SystemExit):publish_vm.build({})
            self.assertEqual(len(run.call_args_list),2)
            self.assertFalse(any('run' in c.args[0][1:2] for c in run.call_args_list))

    def test_second_push_failure_preserves_release_and_removes_auth(self):
        refs={'APP':'fra.ocir.io/publisher/app:v1','PROXY':'fra.ocir.io/publisher/proxy:v1'}
        v={'REGISTRY':'fra.ocir.io','OCIR_NAMESPACE':'publisher','OCIR_USERNAME':'Default/user','IMAGE_PULL_AUTH':'public'}
        paths=[]
        def execute(cmd,**kwargs):
            if cmd[1]=='image':
                ref=cmd[-1]
                return SimpleNamespace(stdout=json.dumps([{'Os':'linux','Architecture':'amd64','RepoDigests':[ref.rsplit(':',1)[0]+'@sha256:'+'a'*64]}]))
            if cmd[1]=='--config':
                paths.append(Path(cmd[2]))
                self.assertEqual((Path(cmd[2])/'config.json').stat().st_mode & 0o777,0o600)
                self.assertNotIn('secret-token',' '.join(cmd))
                if 'login' in cmd:self.assertEqual(kwargs['input'],'secret-token\n')
                if 'push' in cmd and cmd[-1]==refs['PROXY']:raise SystemExit('simulated push failure')
            return SimpleNamespace(stdout='',returncode=0)
        with patch.object(publish_vm,'refs',return_value=refs),patch.object(publish_vm.getpass,'getpass',return_value='secret-token'),patch.object(publish_vm,'run',side_effect=execute),patch.object(publish_vm,'verify_remote'),patch.object(publish_vm,'write_release') as release:
            with self.assertRaises(SystemExit):publish_vm.push(v)
            release.assert_not_called()
        self.assertTrue(paths)
        self.assertTrue(all(not p.exists() for p in paths))


class WorkstationPullTests(unittest.TestCase):
    refs = ['fra.ocir.io/test/app@sha256:' + 'a' * 64, 'fra.ocir.io/test/proxy@sha256:' + 'b' * 64]

    def release(self, root, refs=None, mode='public'):
        refs = refs or self.refs
        (root / 'images.env').write_text('APP_IMAGE=' + refs[0] + '\nPROXY_IMAGE=' + refs[1] + '\nIMAGE_PULL_AUTH=' + mode + '\n')

    def test_rejects_private_or_unpinned_release_before_download(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(pull_images, 'ROOT', Path(folder)), patch.object(pull_images, 'run') as run:
            for refs, mode in [(self.refs, 'private'), (['fra.ocir.io/test/app:latest', self.refs[1]], 'public')]:
                self.release(Path(folder), refs, mode)
                with self.assertRaises(SystemExit): pull_images.pull_images()
            run.assert_not_called()

    def test_public_pull_verifies_local_images_and_preserves_digest_without_engine(self):
        pulls, inspected = [], []
        def execute(cmd, **kwargs):
            self.assertEqual(cmd[:5], ['skopeo', '--override-os', 'linux', '--override-arch', 'amd64'])
            self.assertNotIn('sudo', cmd)
            target = Path(cmd[-1].removeprefix('dir:'))
            self.assertTrue(target.is_dir())
            if cmd[5] == 'copy':
                self.assertIn('--src-no-creds', cmd)
                self.assertIn('--src-tls-verify=true', cmd)
                self.assertIn('--preserve-digests', cmd)
                pulls.append(cmd[-2].removeprefix('docker://'))
                return SimpleNamespace(stdout='')
            inspected.append(target)
            return SimpleNamespace(stdout=json.dumps(dict(Os='linux', Architecture='amd64', Digest='sha256:' + target.name)))
        with tempfile.TemporaryDirectory(prefix='client with spaces ') as folder, patch.object(pull_images, 'ROOT', Path(folder)), patch.object(pull_images, 'run', side_effect=execute), redirect_stdout(io.StringIO()):
            self.release(Path(folder)); pull_images.pull_images()
            self.assertTrue(all(p.is_relative_to((Path(folder)/'local/images').resolve()) for p in inspected))
        self.assertEqual(pulls, self.refs)
        self.assertEqual(len(inspected), 2)

    def test_wrong_digest_or_arch_stops_before_second_copy(self):
        for record in [dict(Os='linux', Architecture='arm64', Digest='sha256:' + 'a' * 64),
                       dict(Os='linux', Architecture='amd64', Digest='sha256:' + 'b' * 64)]:
            with tempfile.TemporaryDirectory() as folder, patch.object(pull_images, 'ROOT', Path(folder)), patch.object(pull_images, 'run', side_effect=[SimpleNamespace(stdout=''), SimpleNamespace(stdout=json.dumps(record))]) as run:
                self.release(Path(folder))
                with self.assertRaises(SystemExit): pull_images.pull_images()
                self.assertEqual(run.call_count, 2)


class PackageChecksumTests(unittest.TestCase):
    def test_detects_tampered_and_missing_files(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            root = Path(folder)
            (root/'a.txt').write_bytes(b'original')
            digest = verify_package.hashlib.sha256(b'original').hexdigest()
            (root/'SHA256SUMS').write_text(digest + '  a.txt\n')
            verify_package.verify(root)
            (root/'a.txt').write_bytes(b'changed')
            with self.assertRaises(ValueError): verify_package.verify(root)
            (root/'a.txt').unlink()
            with self.assertRaises(ValueError): verify_package.verify(root)

    def test_rejects_malformed_or_external_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for record in ['invalid', 'a'*64 + '  ../outside', '']:
                (root/'SHA256SUMS').write_text(record + '\n')
                with self.assertRaises(ValueError): verify_package.verify(root)


if __name__ == '__main__': unittest.main()
