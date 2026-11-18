# Cloud Shell: üzemeltetés és hibakeresés

Az első telepítés sorrendje: [GUIDE.hu.md](GUIDE.hu.md). Ezeket a lépéseket csak a megfelelő művelethez használd. A parancsokat Cloud Shellben, a repo KubernetesApplications könyvtárából futtasd; kivétel az alább külön jelzett, saját gépen végzett HTTP-próba. Új sessionben előbb a guide 10. pontját kövesd. Más namespace választásakor a kézi kubectl parancsokban is cseréld az oci-ai-k8s nevet.

## Hálózati kapcsolatok

A saját infrastruktúrában ellenőrizd a következő kapcsolatokat. A szabályok az erőforráshoz rendelt NSG-ben vagy a subnetjéhez rendelt Security Listben lehetnek; külön NSG létrehozása nem előfeltétel.

| Forrás → cél | Szükséges kapcsolat |
| --- | --- |
| Cloud Shell Private Network → OKE privát API-végpont | TCP/6443 |
| Cloud Shell privát subnet → OCI CLI által használt OCI API-k | HTTPS/443, megfelelő service gateway vagy NAT útvonal |
| Worker node-ok → OCIR | HTTPS/443, képletöltés |
| LiteLLM pod → GenAI | HTTPS/443 |
| LiteLLM és DB-előkészítő pod → PostgreSQL | TCP/5432, illetve a saját `DB_PORT`, TLS |
| Meglévő OCI LB → mindegyik használható worker node | TCP/30080, illetve a választott `NODE_PORT` |
| Böngésző → meglévő LB listener | A kiválasztott HTTP/HTTPS listener portja |

**A PostgreSQL forrásengedélyét ne a régi LiteLLM VM IP-jére állítsd.** OKE-n a DB által látott forrás a CNI/SNAT-beállítástól függően node- vagy podcím lehet. Az infrastruktúra gazdája a cluster hálózati típusához tartozó worker/pod NSG-t vagy megfelelő privát subnet CIDR-t engedélyezze a DB NSG-jében; a forrásoldali egress és az útvonal is kell. Ugyanabban a VCN-ben sem ad automatikusan hozzáférést a subnet neve. A guide 6. pontjának Jobja a tényleges podhálózatból tesztel.

**Az LB → NodePort kapcsolathoz:** az LB NSG-jében stateful egress TCP a worker node-ok privát címeire a választott NodePorton; a worker node-okhoz rendelt NSG-ben stateful ingress ugyanarra a portra az LB NSG-jéből, Source type: NSG. **Ha az LB-n nincs NSG:** az LB subnetjének security listjében legyen megfelelő egress; a worker ingress forrása az LB subnetjének CIDR-je, Source type: CIDR. Több LB-subnet esetén mindet vedd figyelembe. Source port: All; Destination port: a választott NodePort. A workeroldali szabály a hozzá rendelt NSG-ben vagy subnet security listben is lehet. A meglévő node↔pod és node↔node clusterforgalmat a NodePort cluster-szintű továbbításához is meg kell őrizni. NetworkPolicy használata esetén a DNS-t, app → LiteLLM-et, a DB-t és a GenAI-t is engedni kell; a csomag nem írja felül a cluster meglévő hálózati szabályait.

## Alkalmazásellenőrzés az LB megkerülésével

```bash
python3 tools/workshop.py status
python3 tools/workshop.py verify
kubectl get nodes -o wide
```

Elvárt: `litellm` és `streamlit` deployment egy-egy Ready poddal; a LiteLLM Service `ClusterIP`, a Streamlité `NodePort`. A böngészős címet a meglévő OCI LB fogja biztosítani.

A `verify` az app-podból ellenőrzi a Streamlit health végpontját és az app → LiteLLM kapcsolatot. Az LB → NodePort útvonalat a guide 8. pontjának Healthy backendjei és a böngészős próba igazolják.

A `kubectl get nodes -o wide` aktuális **INTERNAL-IP** címeit jegyezd fel az LB beállításához. A Service `externalTrafficPolicy: Cluster` beállításával bármely használható worker továbbíthat az app-podhoz, ezért egy app-pod mellett is megadható több worker backendként. [Kubernetes NodePort](https://kubernetes.io/docs/concepts/services-networking/service/)

## Frissítés és újraindítás

A sémamigráció módosíthatja a táblákat. LiteLLM-verzióváltás előtt a DB gazdájával legyen egyeztetett mentés és visszaállítás; egy Deployment-image visszacserélése nem állítja vissza a DB sémáját.

1. Az oktatótól kapott új kiadás `images.env` fájlja legyen elérhető a Git-repóban; ez az OCIR-ben már elérhető képek pontos címeit tartalmazza.
2. Frissítsd a Cloud Shellben lévő klónodat a guide 2. pontja szerint. A `python3 tools/workshop.py use-published-images` paranccsal vedd át az új képhivatkozásokat. Ellenőrizd a contextet a guide 3. pontja szerint; az új képeket az OKE tölti le.
3. Állítsd le az appot, majd a LiteLLM-et, és várd meg a podok leállását:

```bash
kubectl -n oci-ai-k8s scale deployment/streamlit --replicas=0
kubectl -n oci-ai-k8s wait --for=delete pod -l app.kubernetes.io/name=streamlit --timeout=120s
kubectl -n oci-ai-k8s scale deployment/litellm --replicas=0
kubectl -n oci-ai-k8s wait --for=delete pod -l app.kubernetes.io/name=litellm --timeout=120s
python3 tools/workshop.py prepare
bash scripts/install.sh
```

A `prepare` megőrzi a DB-jelszót, master/salt és appkulcsot; új kulcsot nem generál. A telepítés újrafuttatja a migrációs Jobot és visszaállítja az egy-egy példányt. A frissítés kieséssel jár; az egy példányos workshop nem biztosít folyamatos rendelkezésre állást.

Csak pod-újraindítás, változatlan képpel és DB-sémával:

```bash
kubectl -n oci-ai-k8s rollout restart deployment/litellm
kubectl -n oci-ai-k8s rollout status deployment/litellm --timeout=900s
kubectl -n oci-ai-k8s rollout restart deployment/streamlit
python3 tools/workshop.py verify
```

## Hibakeresés

```bash
python3 tools/workshop.py status
kubectl -n oci-ai-k8s get events --sort-by=.lastTimestamp
kubectl -n oci-ai-k8s logs deployment/litellm --tail=80
kubectl -n oci-ai-k8s logs deployment/streamlit --tail=80
kubectl -n oci-ai-k8s logs job/db-check-db
kubectl -n oci-ai-k8s logs job/litellm-migrate
```

A naplót helyben nézd meg; credentialt, teljes Secretet, kubeconfigot és teljes alkalmazásnaplót ne küldj chatbe vagy Gitbe.

| Jelenség | Teendő |
| --- | --- |
| `localhost:8080` | Saját kubeconfig létrehozása és helyes `KUBECONFIG`, guide 3. pont. |
| OKE API timeout | Cloud Shell Private Network legyen aktív, a kubeconfig PRIVATE_ENDPOINT-tel készüljön. A privát subnet → API útvonal, forrásengedély és a kétoldali TCP/6443 szabály legyen megfelelő. |
| GitHub-frissítés nem működik privát hálón | Ha nincs internetkimenet, a git pull idejére válts Public Networkre, majd a kubectl/telepítőparancsok előtt vissza Private Networkre. |
| `oci` / `kubectl` nem található | Ellenőrizd, hogy Cloud Shellben vagy-e. A guide 1. pontjának eszközei előre telepítettek. |
| OCI CLI hitelesítési hiba | Nyiss új Cloud Shell sessiont. A CLI a Cloud Shell saját hitelesítését használja; ne állítsd át a LiteLLM kulcsára. |
| `prepare`: általános helyi fájlhiba, miközben a CA és PEM ellenőrzése sikerül; MD5-próba `ValueError` | A régi script alapértelmezett MD5-hívását a korlátozott Python elutasíthatja. A javított `tools/workshop.py` az OCI-kulcs azonosítóját `hashlib.md5(public.stdout, usedforsecurity=False)` hívással számítja. Vedd át a javított csomagot, majd ismételd meg a `prepare` lépést. A fingerprint egyezésének ellenőrzése megmarad; a rendszer kriptográfiai házirendjét nem kell átállítani. |
| `tools/workshop.py` nem található / `FileNotFoundError` | Futtasd: `cd ~/ocitestdrivebudapest/KubernetesApplications`, majd ismételd meg a parancsot. Új Cloud Shell session gyakran a home könyvtárban indul. |
| `ImagePullBackOff` | A kiadott `images.env` pontos címei, mindkét repository Public hozzáférése és node → OCIR HTTPS/443 elérés. A nyilvános workshophoz nem kell token; az oktató ellenőrizze az anonim letöltést. |
| Pod `Pending` | Pod describe és events: szabad CPU/memória, amd64 node, taint, ResourceQuota, image méret / tárhely. |
| DB timeout | A podhálózatból engedett DB-port, CNI/SNAT szerinti forrás és DNS, nem a régi VM engedélye. |
| DB TLS hiba | Saját primary FQDN és ugyanahhoz a DB systemhez letöltött CA. Ne kapcsold ki a TLS-ellenőrzést. |
| `password authentication failed for user "litellm_k8s"` | A PostgreSQL szerver válaszolt; ez hitelesítési hiba. Ellenőrizd a DB_HOST/DB_USER értékeket, a user létét és a hozzá tartozó mentett alkalmazásjelszót. Ha csak a managed DB system készült el, a guide 6. pontjának `init-db` lépése is kell. |
| Schema CREATE / DB-tulajdonosi hiba | A DB a megadott alkalmazásuser tulajdonában legyen, és működjön a `public` CREATE joga. A guide bootstrapja kezeli a DB létrehozásához szükséges átmeneti SET ROLE jogot. |
| Hibás DB-jelszó vagy megváltoztatott DB-cél | A csomag nem forgat automatikusan mentett hitelesítőket. Az első kísérlet javításához egyeztess az oktatóval; meglévő futó telepítés `local` állapotát ne töröld. |
| `litellm-migrate` failed | Logs és DB-adminnal egyeztetés; ne használj `db push --accept-data-loss`, migration-reset vagy vak migrate-resolve parancsot. |
| `OOMKilled` | Memóriaigény és nodekapacitás ellenőrzése; a generátorban emeld a megfelelő erőforráshatárt és renderelj újra. |
| LB unhealthy | Backend a worker INTERNAL-IP és a választott NodePort, HTTP health path `/_stcore/health`; LB/node NSG vagy subnet security list, cluster továbbítás. |
| LB health `Pending` | Friss beállítás után várd meg a Console következő, hárompercenkénti health frissítését. Ez nem ugyanaz, mint egy Kubernetes-pod Pending állapota. |
| Backend Healthy, de a böngésző nem éri el az appot | Az alábbi LB-elérés próbát kövesd: helyes HTTP/8080 listener és URL, böngésző → LB forrásengedély, majd klienshálózat és útvonal. |
| Régi `db-diagnose` Job/pod Failed/Error, miközben az új db-check és migrate Complete, mindkét app Ready | A korábbi diagnosztika eredménye megmaradhat. Az aktuális `verify` és a friss Jobok eredménye alapján dönts; a régi hibás Job miatt ne telepíts újra. |
| App megnyílik, de nincs chatkapcsolat | Listener/köztes proxy WebSocket-támogatása, idle timeout, valamint az APP_PUBLIC_HOST/PORT és a tényleges böngészős cím egyezése. A CORS/XSRF védelmet ne kapcsold ki. |
| Modellhívás 401/403 | Appkulcs és modellalias; OCI API user, fingerprint, compartment, modell és meglévő GenAI-hozzáférés. |
| Modellhívás 429 | Virtuális kulcs 10 RPM limitje vagy OCI-kvóta; várj. |
| Nincs spend sor | Aszinkron naplóírás; várj, és csak a DB-t olvasó ellenőrzést ismételd. |

Ha megszakadt az `init-db`: nézd meg a `db-init-db` Jobot. Aktív Jobot ne indíts párhuzamosan; befejezés vagy hiba után a `db-admin-once` Secretet távolítsd el, ha a script takarítása nem tudott lefutni. A Jobot is töröld, ha már nincs rá szükség. Az adminparancs nem fut újra magától. Normál hibakezeléskor a script már törli a Jobot és az átmeneti Secretet; ilyenkor a Job naplójára kapott `NotFound` várható.

### DB-kapcsolatpróba

`OperationalError` esetén először a podból ellenőrizd a TCP-kapcsolatot. Cloud Shell Private Network legyen aktív, és a guide szerinti `KUBECONFIG` legyen beállítva. Az alábbi parancs a `settings.env` DB-címét és kiadott képét használja, egy átmeneti podot indít, majd eltávolítja. Nem kér DB-jelszót, nem futtat SQL-t.

```bash
cd ~/ocitestdrivebudapest/KubernetesApplications
python3 - <<'PY'
import sys
sys.path.insert(0, 'tools')
import workshop as w
v = w.settings()
code = 'import socket,sys; s=socket.create_connection((sys.argv[1],int(sys.argv[2])),10); s.close(); print("PASS: PostgreSQL TCP-kapcsolat")'
w.Cluster(v).command(['run', 'db-tcp-check', '--image=' + v['PROXY_IMAGE'],
    '--restart=Never', '--rm', '-i', '--pod-running-timeout=90s', '--command', '--',
    'python', '-c', code, v['DB_HOST'], v['DB_PORT']], capture=False)
PY
```

`TimeoutError` esetén a node/pod → DB hálózati utat, NSG/security list és egress szabályokat ellenőrizd. `gaierror` esetén a DB-címet és DNS-t. `ConnectionRefusedError` esetén a célcímet, portot és a DB állapotát. Image-letöltési vagy podindítási hiba még nem DB-hálózati eredmény. A `PASS` egy pod TCP-elérését igazolja; a CA, jelszó, adatbázis és jogosultságok ellenőrzése ezután következik. Az `init-db` hibája részleges DB-létrehozás után is jelentkezhet: a mentett `local/credentials.json` fájlt ne töröld.

Ha az átmeneti pod túl gyorsan végez, a kubectl `couldn't attach ... falling back to streaming logs` figyelmeztetést írhat. A mögötte megjelenő `PASS: PostgreSQL TCP-kapcsolat` és a pod törlése sikeres próbát jelent; a figyelmeztetés önmagában nem DB-hiba.

**Ha már PostgreSQL `password authentication failed` választ kaptál:** a kapcsolat eljutott a szerverig. A külön DB- és OKE-subnet, illetve a Cloud Shell Private Network önmagában nem okozza ezt a jelszóhibát. Ellenőrizd, hogy a megfelelő DB_HOST és DB_USER szerepel-e a konfigurációban. A szerveroldali napló több információt adhat, mint a kliens hibája. [PostgreSQL hitelesítési hibák](https://www.postgresql.org/docs/16/client-authentication-problems.html)

Első telepítésnél, ha csak a managed DB systemet hoztad létre, és az `init-db` még nem futott sikeresen, futtasd külön-külön, és csak siker után menj tovább:

```bash
cd ~/ocitestdrivebudapest/KubernetesApplications
python3 tools/workshop.py init-db
python3 tools/workshop.py prepare-db
kubectl -n oci-ai-k8s logs job/db-check-db
```

Az `init-db` a DB-admin (p01: `labadmin`) PostgreSQL-jelszavát kéri. A hiányzó `litellm_k8s` user a korábbi `prepare` során mentett alkalmazásjelszót kapja. A mai p01 próbánál a hiányzó user és adatbázis létrehozása után a kapcsolatpróba sikerült. Ez nem jelenti, hogy minden ilyen hiba oka a hiányzó user: meglévő user hibás jelszavát az `init-db` nem írja át. Meglévő telepítésnél a DB gazdájával ellenőrizd a felhasználót és a hozzá tartozó jelszót; őrizd meg a `local` állapotot és a LiteLLM kulcsokat.

### LB-elérés: Healthy backend, de a böngésző nem csatlakozik

1. A böngészőben a listener pontos címét használd: **`http://REPLACE_LB_ADDRESS:8080/_stcore/health`**. Az elvárt válasz `ok`. A HTTP/8080 listenerhez a puszta IP-cím vagy a HTTPS-cím nem ugyanaz a cél.
2. **LB → Listeners:** legyen HTTP/8080 listener, a default backend set a Kubernetes worker címeket tartalmazza. A régi HTTP/80 VM-listenert hagyd meg. [OCI listener](https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managinglisteners_topic-Creating_Listeners.htm)
3. Ellenőrizd a **böngésző → LB TCP/8080** ingress szabályt a guide 8. pontjával. **NSG nélkül is működik:** az LB subnetjéhez rendelt Security Listben lehet az engedély. A böngésző hálózatának publikus kilépőcímét engedélyezd; a Cloud Shellből elért LB nem igazolja a saját géped hozzáférését.
4. Ha a szabály már megfelelő, ellenőrizd az LB publikus címét és subnetjének internetes útvonalát, majd a klienshálózat kimenő TCP/8080 elérését a hálózat gazdájával. Céges proxy esetén az IP-lekérdező szolgáltatásnál látszó HTTPS-kilépőcím eltérhet a 8080-as kapcsolat forrásától. A timeout önmagában nem bizonyít hibás OCI-szabályt.

**Opcionális pontos HTTP-próba a saját laptop/munkaállomás termináljában (nem Cloud Shellben):** az első sort töltsd ki a böngészőben használt teljes címmel. Ubuntu, Oracle Linux és macOS terminálból ugyanígy futtatható, ha a `curl` elérhető.

```bash
WORKSHOP_APP_URL='http://REPLACE_LB_ADDRESS:8080'
curl --connect-timeout 5 --max-time 10 -sS -o /dev/null -w 'HTTP-kod: %{http_code}\n' "$WORKSHOP_APP_URL/_stcore/health"
```

P01-nél az első sor: `WORKSHOP_APP_URL='http://92.5.181.255:8080'`. Elvárt: `HTTP-kod: 200`. Ez a próba nem hív GenAI-modellt.

| Eredmény | Következő ellenőrzés |
| --- | --- |
| `200`, de az app chatje nem kapcsolódik | A WebSocket-kapcsolat és listener idle timeout; a health kérés önmagában ezt nem teszteli. |
| `000` és timeout | Nem érkezett HTTP-válasz. Listener, forrás-CIDR és ingress, publikus útvonal, kliensoldali kimenő hozzáférés. |
| `000` és connection refused | TCP-elutasítás történt. Először a pontos IP-t, protokollt, listener portját és állapotát ellenőrizd. |
| HTTP-válasz, például `404`, `502`, `503` | A kérést HTTP-kiszolgáló fogadta. Ellenőrizd az útvonalat, a listener backend setjét és a backendeket. |

Az OK backend státusz és a kliensoldali elérés külön ellenőrzés. [OCI LB health hibakeresés](https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/understanding_health_issues.htm)

### Hitelesítők megőrzése

Ha a virtuális kulcs létrehozása bizonytalanul szakadt meg, a `local/key-create-attempt.json` szándékosan blokkolja a vak újrapróbálást. A LiteLLM kulcslistájában ellenőrizd a namespace-hez tartozó `...-streamlit` aliast, és egyeztesd a helyreállítást. A master/salt kulcsot ne generáld újra.

Az OCI API-kulcs fingerprintje MD5-alapú azonosító. A `usedforsecurity=False` ezt az azonosítószámítást jelöli; az API-kérések aláírását és a PostgreSQL TLS-ellenőrzését nem módosítja. [Python hashlib](https://docs.python.org/3.12/library/hashlib.html), [OCI API-kulcs fingerprint](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/apisigningkey.htm).

## A workshop eltávolítása

Csak a saját namespace-ed és a hozzá tartozó dedikált LB-listener/backend set eltávolítását végezd. Előbb az OCI Console-ban vedd ki az ehhez a csomaghoz felvett külön listenert/backend setet, majd:

```bash
kubectl -n oci-ai-k8s get deployments,services,jobs
kubectl delete namespace oci-ai-k8s
```

Ez törli a namespace Kubernetes-erőforrásait, a Secreteket is. A külső PostgreSQL adatait, az OCI Load Balancert és az oktató által közösen kiadott OCIR-képeket nem törli. Ezek életciklusát külön kezeli az infrastruktúra gazdája. A `local` mentés credentialöket tartalmaz; a workshop után a saját titokkezelési rend szerint kezeld.
