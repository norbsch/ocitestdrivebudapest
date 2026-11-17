"""Kubernetes manifests as native JSON objects. No third-party local packages."""
from copy import deepcopy

PART = 'oci-ai-kubernetes'


def labels(name):
    return {'app.kubernetes.io/name': name, 'app.kubernetes.io/part-of': PART}


def resource(kind, name, namespace):
    return dict(apiVersion='v1', kind=kind,
                metadata=dict(name=name, namespace=namespace, labels=labels(name)))


def namespace(name):
    obj = resource('Namespace', name, name)
    del obj['metadata']['namespace']
    return obj


def pod(settings, name, image, proxy=False):
    container = dict(name=name, image=image, imagePullPolicy='Always',
        securityContext=dict(allowPrivilegeEscalation=False, capabilities=dict(drop=['ALL']),
                             readOnlyRootFilesystem=not proxy),
        ports=[dict(name='http', containerPort=4000 if proxy else 8501)],
        resources=dict(requests=dict(cpu='500m' if proxy else '250m', memory='1Gi' if proxy else '256Mi'),
                       limits=dict(cpu='2' if proxy else '1', memory='4Gi' if proxy else '1Gi')),
        volumeMounts=[dict(name='tmp', mountPath='/tmp')])
    spec = dict(automountServiceAccountToken=False, nodeSelector={'kubernetes.io/arch': 'amd64'},
        securityContext=dict(runAsNonRoot=True, runAsUser=10001, runAsGroup=10001,
                             fsGroup=10001, seccompProfile=dict(type='RuntimeDefault')),
        imagePullSecrets=[dict(name='ocir-pull')], terminationGracePeriodSeconds=60,
        containers=[container], volumes=[dict(name='tmp', emptyDir={})])
    if proxy:
        container['envFrom'] = [dict(configMapRef=dict(name='workshop-config')),
                               dict(secretRef=dict(name='litellm-auth'))]
        container['env'] = [dict(name='OCI_KEY_FILE', value='/run/oci/oci-api-key.pem'),
                            dict(name='WORKSHOP_KEY_ALIAS', value=settings['NAMESPACE'] + '-streamlit'),
                            dict(name='STORE_MODEL_IN_DB', value='False')]
        container['volumeMounts'] += [dict(name='proxy-config', mountPath='/etc/workshop', readOnly=True),
            dict(name='oci-key', mountPath='/run/oci', readOnly=True),
            dict(name='db-ca', mountPath='/run/db-ca', readOnly=True)]
        spec['volumes'] += [dict(name='proxy-config', configMap=dict(name='litellm-config')),
            dict(name='oci-key', secret=dict(secretName='oci-api-key', defaultMode=288)),
            dict(name='db-ca', configMap=dict(name='postgres-ca', defaultMode=292))]
    else:
        container['env'] = [dict(name='LITELLM_BASE_URL', value='http://litellm:4000'),
            dict(name='LITELLM_MODEL', value='oci-cohere'),
            dict(name='STREAMLIT_BROWSER_SERVER_ADDRESS', value=settings['APP_PUBLIC_HOST']),
            dict(name='STREAMLIT_BROWSER_SERVER_PORT', value=settings['APP_PUBLIC_PORT'])]
        container['envFrom'] = [dict(secretRef=dict(name='streamlit-auth'))]
    return spec


def probe(path):
    return dict(httpGet=dict(path=path, port='http'), periodSeconds=10, timeoutSeconds=5, failureThreshold=3)


def deployment(settings, name, image, proxy=False):
    obj = resource('Deployment', name, settings['NAMESPACE'])
    obj['apiVersion'] = 'apps/v1'
    spec = pod(settings, name, image, proxy)
    container = spec['containers'][0]
    container['livenessProbe'] = probe('/health/liveliness' if proxy else '/_stcore/health')
    container['readinessProbe'] = probe('/health/readiness' if proxy else '/_stcore/health')
    container['startupProbe'] = deepcopy(container['livenessProbe'])
    container['startupProbe']['failureThreshold'] = 60
    obj['spec'] = dict(replicas=1, strategy=dict(type='Recreate'), progressDeadlineSeconds=900,
        selector=dict(matchLabels=labels(name)),
        template=dict(metadata=dict(labels=labels(name)), spec=spec))
    return obj


def service(settings, name, node_port=None):
    obj = resource('Service', name, settings['NAMESPACE'])
    obj['spec'] = dict(type='ClusterIP' if node_port is None else 'NodePort', selector=labels(name),
                       ports=[dict(name='http', protocol='TCP', port=4000 if name == 'litellm' else 80, targetPort='http')])
    if node_port is not None:
        obj['spec']['ports'][0]['nodePort'] = int(node_port)
        obj['spec']['externalTrafficPolicy'] = 'Cluster'
    return obj


def job(settings, image, action):
    name = 'db-' + action if action in ['check-db', 'init-db'] else 'litellm-migrate'
    obj = resource('Job', name, settings['NAMESPACE'])
    obj['apiVersion'] = 'batch/v1'
    spec = pod(settings, name, image, proxy=True)
    spec['restartPolicy'] = 'Never'
    container = spec['containers'][0]
    container.pop('ports')
    container['args'] = [action]
    if action == 'init-db':
        container['env'].append(dict(name='DB_ADMIN_PASSWORD', valueFrom=dict(secretKeyRef=dict(name='db-admin-once', key='DB_ADMIN_PASSWORD'))))
    obj['spec'] = dict(backoffLimit=0, activeDeadlineSeconds=600,
        template=dict(metadata=dict(labels=labels(name)), spec=spec))
    return obj


def images(settings):
    prefix = settings['REGISTRY'] + '/' + settings['OCIR_NAMESPACE'] + '/'
    return {key: prefix + settings[key + '_REPOSITORY'] + ':' + settings['IMAGE_TAG'] for key in ['APP', 'PROXY']}


def all_manifests(settings):
    refs = images(settings)
    return {
        'namespace': namespace(settings['NAMESPACE']),
        'litellm-service': service(settings, 'litellm'),
        'litellm-deployment': deployment(settings, 'litellm', refs['PROXY'], proxy=True),
        'streamlit-service': service(settings, 'streamlit', settings['NODE_PORT']),
        'streamlit-deployment': deployment(settings, 'streamlit', refs['APP']),
        'db-check': job(settings, refs['PROXY'], 'check-db'),
        'db-init': job(settings, refs['PROXY'], 'init-db'),
        'litellm-migrate': job(settings, refs['PROXY'], 'migrate'),
    }
