# Cloud Shell: üzemeltetés és hibakeresés

Az első telepítés sorrendje: [GUIDE.hu.md](GUIDE.hu.md). Ezeket a lépéseket csak a megfelelő művelethez használd. A parancsokat Cloud Shellben, a repo KubernetesApplications könyvtárából futtasd. Új sessionben előbb a guide 10. pontját kövesd. Más namespace választásakor a kézi kubectl parancsokban is cseréld az oci-ai-k8s nevet.

## Hálózati kapcsolatok

A saját infrastruktúrában ellenőrizd a következő kapcsolatokat. A megfelelő NSG-k ténylegesen legyenek a cél-erőforrásokhoz rendelve.

| Forrás → cél | Szükséges kapcsolat |
| --- | --- |
| Cloud Shell → választott OKE API-végpont | TCP/6443 |
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
| OKE API timeout | A választott publikus/privát végponthoz működő útvonal, Cloud Shell tényleges forrásengedélye, kimenő és bejövő TCP/6443. |
| `oci` / `kubectl` nem található | Ellenőrizd, hogy Cloud Shellben vagy-e. A guide 1. pontjának eszközei előre telepítettek. |
| OCI CLI hitelesítési hiba | Nyiss új Cloud Shell sessiont. A CLI a Cloud Shell saját hitelesítését használja; ne állítsd át a LiteLLM kulcsára. |
| `ImagePullBackOff` | A kiadott `images.env` pontos címei, mindkét repository Public hozzáférése és node → OCIR HTTPS/443 elérés. A nyilvános workshophoz nem kell token; az oktató ellenőrizze az anonim letöltést. |
| `Pending` | Pod describe és events: szabad CPU/memória, amd64 node, taint, ResourceQuota, image méret / tárhely. |
| DB timeout | A podhálózatból engedett DB-port, CNI/SNAT szerinti forrás és DNS, nem a régi VM engedélye. |
| DB TLS hiba | Saját primary FQDN és ugyanahhoz a DB systemhez letöltött CA. Ne kapcsold ki a TLS-ellenőrzést. |
| DB auth / schema-joghiba | A mentett alkalmazásjelszó a megadott DB-userhez tartozzon; a DB legyen ennek tulajdonában és a `public` CREATE joga működjön. A DB-admin jelszó ettől különbözik. |
| Hibás DB-jelszó vagy megváltoztatott DB-cél | A csomag nem forgat automatikusan mentett hitelesítőket. Az első kísérlet javításához egyeztess az oktatóval; meglévő futó telepítés `local` állapotát ne töröld. |
| `litellm-migrate` failed | Logs és DB-adminnal egyeztetés; ne használj `db push --accept-data-loss`, migration-reset vagy vak migrate-resolve parancsot. |
| `OOMKilled` | Memóriaigény és nodekapacitás ellenőrzése; a generátorban emeld a megfelelő erőforráshatárt és renderelj újra. |
| LB unhealthy | Backend a worker INTERNAL-IP és a választott NodePort, HTTP health path `/_stcore/health`; LB/node NSG vagy subnet security list, cluster továbbítás. |
| App megnyílik, de nincs chatkapcsolat | Listener/köztes proxy WebSocket-támogatása, idle timeout, valamint az APP_PUBLIC_HOST/PORT és a tényleges böngészős cím egyezése. A CORS/XSRF védelmet ne kapcsold ki. |
| Modellhívás 401/403 | Appkulcs és modellalias; OCI API user, fingerprint, compartment, modell és meglévő GenAI-hozzáférés. |
| Modellhívás 429 | Virtuális kulcs 10 RPM limitje vagy OCI-kvóta; várj. |
| Nincs spend sor | Aszinkron naplóírás; várj, és csak a DB-t olvasó ellenőrzést ismételd. |

Ha megszakadt az `init-db`: nézd meg a `db-init-db` Jobot. Aktív Jobot ne indíts párhuzamosan; befejezés vagy hiba után a `db-admin-once` Secretet távolítsd el, ha a script takarítása nem tudott lefutni. A Jobot is töröld, ha már nincs rá szükség. Az adminparancs nem fut újra magától.

Ha a virtuális kulcs létrehozása bizonytalanul szakadt meg, a `local/key-create-attempt.json` szándékosan blokkolja a vak újrapróbálást. A LiteLLM kulcslistájában ellenőrizd a namespace-hez tartozó `...-streamlit` aliast, és egyeztesd a helyreállítást. A master/salt kulcsot ne generáld újra.

## A workshop eltávolítása

Csak a saját namespace-ed és a hozzá tartozó dedikált LB-listener/backend set eltávolítását végezd. Előbb az OCI Console-ban vedd ki az ehhez a csomaghoz felvett külön listenert/backend setet, majd:

```bash
kubectl -n oci-ai-k8s get deployments,services,jobs
kubectl delete namespace oci-ai-k8s
```

Ez törli a namespace Kubernetes-erőforrásait, a Secreteket is. A külső PostgreSQL adatait, az OCI Load Balancert és az oktató által közösen kiadott OCIR-képeket nem törli. Ezek életciklusát külön kezeli az infrastruktúra gazdája. A `local` mentés credentialöket tartalmaz; a workshop után a saját titokkezelési rend szerint kezeld.
