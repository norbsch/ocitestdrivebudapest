# Streamlit és LiteLLM telepítése OKE-re Cloud Shellből

Minden parancsot az **OCI Console Cloud Shell termináljában** futtass. A saját gépeden csak böngésző kell. A kész nyilvános OCIR-képeket az OKE worker node-ok töltik le: a Cloud Shell tárhelyére csak a repo, a konfiguráció és néhány kis fájl kerül.

Az OCI CLI beállítja az OKE-hozzáférést. Ezután a csomag telepítőscriptje kubectl-lel telepít egy Streamlit- és egy LiteLLM-podot. A böngésző a meglévő Load Balanceren keresztül éri el az appot; a LiteLLM a saját OCI PostgreSQL 16 adatbázisodat és az OCI Generative AI szolgáltatást használja.

A meglévő infrastruktúrát és az adminisztrátori hozzáférést adottnak vesszük. A számozott pontokon sorban haladj; hibánál állj meg az adott pontnál. A `REPLACE_...` értékeket cseréld a sajátodra. A p01 ismert adatai: [P01.hu.md](P01.hu.md).

## 1 Cloud Shell megnyitása és az OCI CLI ellenőrzése

1. Jelentkezz be az **OCI Console**-ba, és válaszd ki a cluster régióját, például **Germany Central (Frankfurt)**.
2. Jobbra fent **Developer tools / terminál ikon → Cloud Shell**.
3. A Cloud Shell felső **Network** menüjében válaszd a **Public Network** lehetőséget a GitHub-letöltéshez. A repo letöltése után, a 3. pontban **Private Networkre váltunk**, és az OKE privát API-végpontját használjuk.
4. Futtasd:

```bash
oci --version
kubectl version --client
python3 --version
git --version
oci os ns get --query data --raw-output
df -h "$HOME"
```

**Elvárt:** verziószámok, a saját tenancy namespace-e és szabad tárhely. A Python legyen legalább **3.9**. Ha régebbi, futtasd a `csruntimectl python list` parancsot, majd a listában szereplő 3.9 vagy újabb változat aliasával: `csruntimectl python set REPLACE_PYTHON_ALIAS`. Ezután újra `python3 --version`.

Az OCI CLI és a kubectl előre telepített; a CLI a bejelentkezett Console-felhasználót használja. **Itt nincs OCI CLI-telepítés vagy `oci setup config` lépés.** Hagyd meg a Cloud Shell saját hitelesítési környezeti változóit. A LiteLLM futásához szükséges külön API-kulcsot az 5. pontban adod meg. [Cloud Shell](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/cloudshellintro.htm), [beépített hitelesítés és eszközök](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/devcloudshellgettingstarted.htm).

## 2 A telepítőcsomag letöltése GitHubról

Ezt a pontot GitHubot elérő hálózaton végezd. Ha a privát hálózatodon nincs internetkimenet, a klónozás vagy frissítés idejére válaszd a **Public Networköt**, majd a 3. pont előtt válts vissza a privát hálózatra.

Első alkalommal:

```bash
cd ~
git clone https://github.com/norbsch/ocitestdrivebudapest.git
cd ~/ocitestdrivebudapest/KubernetesApplications
python3 tools/verify_package.py
```

Ha a repo már megvan, **a fenti blokk helyett**:

```bash
cd ~/ocitestdrivebudapest
git pull --ff-only origin main
cd KubernetesApplications
python3 tools/verify_package.py
```

**Elvárt:** sikeres csomagellenőrzés. GitHub-token és SSH-kulcs nem szükséges. Frissítési konfliktusnál ne töröld a saját fájljaidat; előbb egyeztesd az oktatóval.

Az oktató a friss csomagot előzetesen tegye fel a repóba. Az `images.env` a két már kiadott, nyilvános OCIR-kép pontos címét tartalmazza. Ezeket a következő lépések használják; résztvevőként nem kell registry-token.

## 3 Privát hálózat és OKE-kapcsolat beállítása

**Először válts a Cloud Shellben a clustert elérő privát hálózatra.** A p01 környezetben ezen keresztül érjük el a Kubernetes API-t. A `kubectl get nodes` az API-t kérdezi le; a worker node-okhoz nem kell SSH-kapcsolat.

Ha már van működő privát hálózati definíciód, a Cloud Shell **Network** menüjében válaszd ki. Ha még nincs:

1. **Network → Private Network Definition List → Create Private Network Definition**.
2. Adj nevet, például `p01-oke-access`.
3. Válaszd a clusterhez hálózati úttal rendelkező compartmentet, VCN-t és subnetet. A p01 esetében: **OCITestDriveBudapest → p01-vcn → p01-subnet-private-vm**. A subnetben legyen szabad IP-cím, és a session Frankfurtban fusson.
4. Ha az infrastruktúra biztosít külön Cloud Shell NSG-t, válaszd ki.
5. Jelöld be a **Use as active network** mezőt, majd **Create**. Várd meg a privát kapcsolat létrejöttét.

A Cloud Shell privát subnetjéből az OKE API **TCP/6443** portja legyen elérhető. A subnet az OCI CLI API-hívásaihoz is kapjon HTTPS/443 útvonalat, például a megfelelő service gatewayen vagy NAT gatewayen át. [Cloud Shell privát hálózat](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/cloudshellintro_topic-Cloud_Shell_Networking.htm)

**OCI Console → Kubernetes Engine → Clusters → saját cluster:** másold ki a cluster OCID-ját. A következő blokk első két sorát töltsd ki, majd **a privát hálózatra kapcsolt Cloud Shellben** futtasd:

```bash
WORKSHOP_CLUSTER_OCID='REPLACE_CLUSTER_OCID'
WORKSHOP_CLUSTER_REGION='eu-frankfurt-1'
umask 077
mkdir -p "$HOME/.kube"
chmod 700 "$HOME/.kube"
export KUBECONFIG="$HOME/.kube/oci-ai-workshop.config"
oci ce cluster create-kubeconfig --cluster-id "$WORKSHOP_CLUSTER_OCID" --file "$KUBECONFIG" --region "$WORKSHOP_CLUSTER_REGION" --token-version 2.0.0 --kube-endpoint PRIVATE_ENDPOINT
chmod 600 "$KUBECONFIG"
kubectl config current-context
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}{"\n"}'
kubectl get nodes --request-timeout=10s -L kubernetes.io/arch,node.kubernetes.io/instance-type
```

**Elvárt:** saját context, a cluster privát API-címe és legalább egy **Ready / amd64** worker. A p01 korábban megadott privát API-címe `https://10.0.0.168:6443`. A context értékét a következő pontban fogod használni. A Cloud Shell lehet ARM vagy AMD gép; a kiadott képekhez a **worker node** legyen AMD64. A kubectl minor verziója legfeljebb eggyel térjen el a clusterétől; a p01 v1.37.1-hez a korábban látott v1.36.4 kliens megfelelő. [OKE-hozzáférés](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengdownloadkubeconfigfile.htm)

**Ha még a korábbi publikus cím jelenik meg:** ellenőrizd a `KUBECONFIG` értékét, és futtasd újra a fenti `create-kubeconfig` parancsot `PRIVATE_ENDPOINT` értékkel. Ez a workshop kubeconfigját frissíti; az OCI-erőforrások hálózatát nem módosítja.

**Ha a privát címre timeoutot kapsz:** ellenőrizd az aktív Private Networköt és az API-végpont NSG-jében a szabályt: **Add ingress rule → Stateful → Source type CIDR → a Cloud Shellhez választott privát subnet CIDR-je → TCP → Source port All → Destination port 6443**. NSG hiányában az API subnet security listjében legyen meg. A CIDR-t az OCI Console subnet adatlapjáról másold ki. A Cloud Shell subnetjének/NSG-jének egress szabálya és az útvonal is engedje a kapcsolatot. Ezután ismételd meg a `kubectl get nodes` parancsot.

## 4 Az alkalmazások adatainak kitöltése

```bash
cd ~/ocitestdrivebudapest/KubernetesApplications
umask 077
mkdir -p local
chmod 700 local
test -f settings.env || cp templates/settings.env.example settings.env
chmod 600 settings.env
python3 tools/workshop.py use-published-images
nano settings.env
```

| Mező | Mit írj bele? |
| --- | --- |
| `KUBE_CONTEXT` | Az előző pont `kubectl config current-context` kimenete. |
| `APP_PUBLIC_HOST` | A meglévő Load Balancer böngészőből elérhető IP-je vagy hostneve, protokoll és port nélkül. |
| `APP_PUBLIC_PORT` | Az apphoz használt listener portja; alapból `8080`. |
| `DB_HOST` | **Databases → PostgreSQL → DB systems → saját DB → primary FQDN**. IP helyett ezt használd a TLS-ellenőrzéshez. |
| `DB_ADMIN` | A PostgreSQL adminfelhasználó neve, p01-nél `labadmin`. |
| `DB_NAME`, `DB_USER` | Alapból mindkettő `litellm_k8s`. A 6. pont létrehozza őket, ha még nincsenek. |
| `OCI_REGION` | A Generative AI régiója, például `eu-frankfurt-1`. |
| `OCI_COMPARTMENT_ID` | A GenAI inference-hez használt compartment OCID-ja. |
| `OCI_MODEL_ID` | A régióban elérhető GenAI-modell; a sablonban `oci/cohere.command-a-03-2025`. |
| `OCI_USER`, `OCI_TENANCY`, `OCI_FINGERPRINT` | Az 5. pontban létrehozott API-kulcs adatai; egyelőre maradhatnak helyőrzők. |

A `NAMESPACE=oci-ai-k8s`, `NODE_PORT=30080` és `DB_PORT=5432` alapérték maradhat, ha nincs ütközés. Az `APP_IMAGE`, `PROXY_IMAGE`, `IMAGE_PULL_AUTH=public` mezőket a parancs már kitöltötte. Az `OCIR_LOGIN` mezőt nyilvános képeknél nem használjuk, maradhat a sablonérték.

A DB system legyen **Active, PostgreSQL 16**. A Kuberneteses LiteLLM külön DB-t és DB-felhasználót használjon a korábbi VM-es telepítéstől. Ne add meg a VM-es LiteLLM adatbázisát.

Nano mentés: **Ctrl+O → Enter → Ctrl+X**. A fájlban `NEV=ertek` alakot használj, idézőjelek és `export` nélkül. Jelszót ne írj bele.

## 5 A LiteLLM OCI API-kulcsa és a PostgreSQL CA feltöltése

**Az API-kulcs a clusterben futó LiteLLM GenAI-hívásaihoz kell.** A Cloud Shell beépített CLI-hitelesítése a Cloud Shellben marad.

1. **OCI Console → Profil → My profile / User settings → API keys / Tokens and keys → Add API key → Generate API key pair**.
2. **Download private key**, majd **Add**. Ha már van saját, hozzáadott API-kulcsod és megvan a hozzá tartozó privát PEM-fájl, azt is használhatod.
3. A **Configuration File Preview** `user`, `tenancy`, `fingerprint` értékeit írd a `settings.env` `OCI_USER`, `OCI_TENANCY`, `OCI_FINGERPRINT` mezőjébe. A preview-t nem kell CLI-configként elmentened.
4. **Databases → PostgreSQL → DB systems → saját DB system → CA certificate / Download certificate**: töltsd le a CA-fájlt a gépedre. A `.pub` kiterjesztés is megfelelő.
5. A Cloud Shell **bal felső menü → Upload → Select from your computer → Upload** lépéseivel töltsd fel a privát PEM-kulcsot és a DB CA-fájlt. Egyenként válaszd ki őket. Jegyezd fel a feltöltési ablakban jelzett célútvonalukat. [API-kulcs](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/apisigningkey.htm), [fájlfeltöltés](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/devcloudshellgettingstarted.htm).

Ha a feltöltés a home könyvtáradba történt, a teljes fájlneveket behelyettesítve futtasd:

```bash
cd ~/ocitestdrivebudapest/KubernetesApplications
chmod 600 "$HOME/REPLACE_API_PRIVATE_KEY_FILENAME" "$HOME/REPLACE_POSTGRES_CA_FILENAME"
mv -i "$HOME/REPLACE_API_PRIVATE_KEY_FILENAME" local/oci-api-key.pem
mv -i "$HOME/REPLACE_POSTGRES_CA_FILENAME" local/postgres-ca.pem
chmod 600 local/oci-api-key.pem local/postgres-ca.pem
openssl pkey -in local/oci-api-key.pem -passin pass: -check -noout
openssl x509 -in local/postgres-ca.pem -noout -subject -dates
nano settings.env
```

Eltérő feltöltési hely esetén a `$HOME/...` helyett a tényleges útvonalat használd. Meglévő, megfelelő célfájlnál a másolási/áthelyezési lépést hagyd ki. A csomag jelszó nélküli PEM API-kulcsot vár; a 600 jogosultság védi a fájlt. API-kulcsot, jelszót és a `local` könyvtár tartalmát ne tedd Gitbe.

**Elvárt:** olvasható privát kulcs, megjelenő CA subject/dátumok, és minden kötelező mező kitöltve a `settings.env` fájlban.

## 6 PostgreSQL előkészítése és kapcsolatpróba

**Az OCI DB system `Active` állapota önmagában nem jelenti, hogy a `litellm_k8s` adatbázis és felhasználó is létezik.** Ha csak a managed DB systemet hoztad létre, ebben a pontban a teljes sorrend: `check` → `prepare` → `init-db` → `prepare-db`. Sikeres DB-kapcsolatpróba után lépj a 7. pontra.

Az infrastruktúrában ezek a kapcsolatok működjenek:

| Forrás → cél | Port |
| --- | --- |
| OKE worker node → OCIR | TCP/443 |
| OKE pod → OCI Generative AI | TCP/443 |
| LiteLLM és DB-előkészítő pod → PostgreSQL | TCP/5432, illetve a saját `DB_PORT` |

A DB NSG-jében vagy a DB subnetjének security listjében a cluster CNI/SNAT szerinti **worker/pod forrást** engedélyezd. A régi LiteLLM VM engedélye nem elég. A DB-kapcsolatot a clusterben futó Job teszteli; a Cloud Shellnek nem kell közvetlen PostgreSQL-elérés. Az OKE és a DB lehet külön subnetben, ha az útvonal és a szabályok engedik a kapcsolatot. Részletes hálózati beállítások: [UZEMELTETES.hu.md](UZEMELTETES.hu.md).

Cloud Shellben:

```bash
cd ~/ocitestdrivebudapest/KubernetesApplications
python3 tools/workshop.py check
python3 tools/workshop.py prepare
```

A `prepare` első futáskor rejtve, kétszer kéri az **alkalmazás DB-felhasználójának jelszavát**. Új `litellm_k8s` userhez válassz új jelszót; meglévő usernél annak jelenlegi jelszavát add meg. A program ellenőrzi az API-kulcs fingerprintjét és a CA-t, majd létrehozza a namespace-t és a szükséges Kubernetes Secreteket/ConfigMapeket. **A `prepare` még nem hoz létre PostgreSQL-adatbázist vagy DB-felhasználót, és nem teszteli a DB-bejelentkezést.** A hitelesítőket a védett `local` könyvtárban is megőrzi; újrafuttatáskor nem cseréli le őket.

| Mikor kér jelszót? | Melyik felhasználóhoz tartozik? |
| --- | --- |
| `prepare`: alkalmazás PostgreSQL-jelszava | `DB_USER`, alapból `litellm_k8s`; új userhez te választod. |
| `init-db`: PostgreSQL DB-admin jelszava | `DB_ADMIN`, p01-nél `labadmin`; az OCI DB system létrehozásakor megadott adminjelszó. |

Az OCI Console bejelentkezési jelszavát vagy OCIR Auth Tokent egyik helyen se add meg. A rejtett bevitel közben karakterek és csillagok sem jelennek meg; beillesztés után nyomj Entert.

**Ha még nincs külön alkalmazás-DB és user:**

```bash
python3 tools/workshop.py init-db
```

Ez a `DB_ADMIN` **PostgreSQL-jelszavát** kéri rejtve. A Job csak a hiányzó DB-t és felhasználót hozza létre, az alkalmazásfelhasználót teszi DB-tulajdonossá, és kezeli az ehhez szükséges átmeneti `SET ROLE` jogot. Az új user a `prepare` során megadott alkalmazásjelszót kapja. Meglévő DB-t/jelszót nem ír felül. A futás végén törli az átmeneti admin Secretet és Jobot. **Elvárt:** `PASS: db-init-db`, majd az átmeneti erőforrások eltávolításának visszajelzése.

Ha `FAIL: OperationalError` jelenik meg, állj meg a [DB-kapcsolatpróbánál](UZEMELTETES.hu.md). A hiba után törölt admin Job naplójára kapott `NotFound` a takarítás következménye. A kapcsolat hibáját külön kell azonosítani.

**Akár új, akár meglévő a DB, ezután kötelező:**

```bash
python3 tools/workshop.py prepare-db
kubectl -n oci-ai-k8s logs job/db-check-db
```

**Elvárt:** `PASS: alkalmazas DB-kapcsolat, PostgreSQL 16, verify-full TLS es schema CREATE jog.` Csak ezután folytasd. A Job az alkalmazásfelhasználóval tesztel, FQDN- és CA-ellenőrzéssel. A LiteLLM táblái a következő pontban készülnek el.

Ha a részletes hiba `password authentication failed for user "litellm_k8s"`, a pod eléri a PostgreSQL szervert, de a bejelentkezés nem sikerül. Első telepítésnél ellenőrizd, hogy az `init-db` sikeresen lefutott-e: hiányzó usernél is jelentkezhet hitelesítési hiba. Ne válts emiatt Cloud Shell subnetet, és ne töröld a mentett `local/credentials.json` fájlt. A további lépések az [üzemeltetési hibakeresésben](UZEMELTETES.hu.md) vannak.

Az első DB-Job indításakor az OKE már automatikusan letölti a LiteLLM-képet az OCIR-ből. Ha más `NAMESPACE` értéket választottál, a kézi `kubectl -n oci-ai-k8s` parancsokban is azt használd.

## 7 A LiteLLM és a Streamlit telepítése

```bash
cd ~/ocitestdrivebudapest/KubernetesApplications
bash scripts/install.sh
python3 tools/workshop.py status
```

A script sorrendben ellenőrzi a DB-t, lefuttatja a LiteLLM migrációs Jobot, elindítja a LiteLLM-et, létrehozza az app korlátozott virtuális kulcsát, majd elindítja a Streamlitet és ellenőrzi a kapcsolatukat. A virtuális kulcs az `oci-cohere` modellhez használható, 10 USD kerettel és 10 kérés/perc limittel.

**Elvárt:** `PASS: a Kubernetes alkalmazasok keszek.` A `litellm` és `streamlit` egy-egy Ready poddal fut. A LiteLLM Service `ClusterIP`, a Streamlité `NodePort`. A befejezett Jobok `Completed` állapota rendben van.

A Kubernetes közvetlenül a nyilvános OCIR-ből tölti le a két rögzített kiadást a worker node-okra. Cloud Shellben nincs több GB-os kép vagy konténerfuttatás. Ez a teszt még nem hívja a fizetős GenAI-modellt.

Ha már fut korábbi LiteLLM deployment, az újratelepítés előtt az [üzemeltetési leírás](UZEMELTETES.hu.md) frissítési lépéseit kövesd; a script élő kiszolgáló mellett nem indít migrációt.

## 8 A meglévő Load Balancer bekötése

Két külön kapcsolatot állítunk be: **böngésző → LB:8080**, illetve **LB → worker:30080 → Streamlit**. A backend health csak a második útvonalat ellenőrzi. **Külön NSG nem kötelező:** az LB subnetjéhez rendelt Security List is biztosíthatja a hozzáférést.

Cloud Shellben kérd le az aktuális worker címeket:

```bash
kubectl get nodes -o wide
```

**OCI Console → Networking → Load Balancers → saját meglévő LB.**

1. **Backend sets → Create backend set**: név `oci-ai-k8s-backends`, policy **Weighted round robin**, **Use SSL kikapcsolva**.
2. Health check: **HTTP**, port **30080**, path **`/_stcore/health`**, status **200**.
3. **Backends → Add backends → IP addresses**: add hozzá minden használható worker **INTERNAL-IP** címét, port **30080**, weight **1**. A worker címét használd, ne a pod vagy a Service IP-jét.
4. Engedd az **LB → worker TCP/30080** forgalmat: worker ingress forrása az LB NSG-je (**Source type NSG**), vagy NSG hiányában az LB subnet CIDR-je (**Source type CIDR**). Az LB-n az egress is legyen engedett. Több LB-subnetnél mindet vedd figyelembe.
5. Várd meg a backendek **OK / Healthy** állapotát. A kezdeti **Pending** után frissítsd az oldalt: a Console health kijelzése **hárompercenként** frissül. Ha ezután sem OK, ellenőrizd az előző három lépést. [OCI health státuszok](https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/understanding_health_issues.htm)
6. **Listeners → Create listener**: név `oci-ai-k8s-http`, protocol **HTTP**, port **8080**, default backend set `oci-ai-k8s-backends`, idle timeout **300 másodperc**. IP-címes eléréshez a hostname maradjon üres; **Use SSL** és **Proxy Protocol** kikapcsolva. A port egyezzen a `settings.env` `APP_PUBLIC_PORT` értékével. A meglévő VM-es HTTP/80 listenert hagyd meg; szabad, kifejezetten ennek az appnak adott 80-as port is használható.

**A böngésző → LB hozzáférés engedélyezése:**

1. A saját géped böngészőjében nyisd meg az [IPv4-címedet mutató oldalt](https://api.ipify.org). Jegyezd fel a címet, és írj mögé `/32`-t. Több résztvevőhöz az infrastruktúra gazdájától kapott résztvevői publikus CIDR-t használd. Ehhez a szabályhoz a böngésző hálózatának kilépőcíme kell, nem a Cloud Shell vagy a worker privát IP-je.
2. **NSG nélküli LB-nél:** az LB adatlapján azonosítsd a hozzá tartozó subnetet → nyisd meg → **Security Lists → hozzárendelt lista → Ingress Rules**. Az **LB subnetjét** válaszd, ne a worker vagy DB subnetjét. Több LB-subnetnél mindegyikhez kell megfelelő szabály. Ha az LB NSG-t használ, a szabályt a hozzá rendelt NSG-ben is megadhatod.
3. Ha a forrásodra és a 8080-as célportra már van engedély, ne duplikáld. Egyébként **Add Ingress Rules**:

| Mező | Érték |
| --- | --- |
| Stateless | Ne legyen bepipálva; így stateful a szabály. |
| Source Type | `CIDR` |
| Source CIDR | A böngésző publikus kilépőcíme `/32`-vel, vagy a résztvevői publikus CIDR. |
| IP Protocol | `TCP` |
| Source Port Range | `All` |
| Destination Port Range | `8080`, illetve a választott `APP_PUBLIC_PORT`. |

A listener létrehozásától ez a hálózati engedély még nem lesz automatikusan megfelelő. A Security List szabályai a hozzárendelt subnet erőforrásaira vonatkoznak. [OCI Security Lists](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securitylists.htm)

Más `NODE_PORT` értéknél a 30080-at mindenhol cseréld arra. A p01 LB-n nincs NSG, ott a subnet security listjét használd; új NSG-t nem kell létrehozni. A Streamlit WebSocket-kapcsolatát a köztes proxyk is engedjék. [OCI LB backend set](https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managingbackendsets_topic-Creating_Backend_Sets.htm), [listener létrehozása](https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managinglisteners_topic-Creating_Listeners.htm)

Privát LB esetén a böngészőt futtató gépnek hálózati elérés kell az LB-hez.

Egy app-pod mellett is lehet több worker backend, mert a Service cluster-szinten továbbít. A kézi backendlista nem követi a worker IP-cseréjét; ilyenkor frissítsd.

## 9 Böngészős próba és az adatbázis naplójának ellenőrzése

1. A saját géped böngészőjében először nyisd meg: **`http://REPLACE_LB_ADDRESS:8080/_stcore/health`**. A p01 címe: **`http://92.5.181.255:8080/_stcore/health`**. Elvárt: **`ok`**. Ez még nem hív modellt. Pontosan a beállított protokollt és portot használd; a HTTP/8080 listenerhez az `http://` és a `:8080` is kell.
2. Ha timeout vagy `refused to connect` jelenik meg, állj meg az [LB-elérés hibakeresésénél](UZEMELTETES.hu.md). A Healthy backend önmagában nem igazolja a böngésző elérését.
3. Ha a health válasz jó, nyisd meg az alkalmazást: **`http://REPLACE_LB_ADDRESS:8080`**, p01-nél **`http://92.5.181.255:8080`**. Meglévő HTTPS listener esetén annak címét és portját használd a health próbához is.
4. A chatmezőben küldj egy rövid kérdést: `Válaszolj egy szóval: működik?`
5. Ellenőrizd a választ, a tokenhasználatot és a becsült költséget.

Ez **fizetős OCI GenAI-hívás**. A megjelenő költség a `proxy/config.yaml` demóáraiból számított becslés. Az OCI-kulcs, DB-jelszó és LiteLLM master key a böngészőhöz nem kerül.

Ha egy konkrét kérés PostgreSQL naplósorát is ellenőriznéd, Cloud Shellben indíts egy **külön, fizetős** tesztkérést:

```bash
python3 tools/workshop.py smoke
python3 tools/workshop.py verify-spend
```

**Elvárt:** modellválasz és call ID, majd ugyanahhoz a call ID-hoz pozitív spend sor a DB-ben. Ha a sor még nem látszik, várj egy percet, és **csak a `verify-spend` parancsot ismételd**. Ez nem küld új modellkérést.

## 10 Folytatás új Cloud Shell sessionből

Nyisd meg ugyanazzal az OCI-felhasználóval és ugyanabban a Cloud Shell régióban. A **Network** menüben válaszd a 3. pontban beállított **privát hálózatot**, majd:

```bash
cd ~/ocitestdrivebudapest/KubernetesApplications
export KUBECONFIG="$HOME/.kube/oci-ai-workshop.config"
kubectl config current-context
kubectl get nodes --request-timeout=10s
```

A context egyezzen a `settings.env` értékével. Folytasd az utolsó sikeres pont után; őrizd meg a meglévő `settings.env` és `local` fájlokat. A `local` hitelesítőiről legyen védett mentésed. Sessionbontás után az OKE-n futó appok tovább működnek.

Frissítés, hibaelhárítás, hálózati részletek és eltávolítás: [UZEMELTETES.hu.md](UZEMELTETES.hu.md).
