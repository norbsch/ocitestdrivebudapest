# Streamlit és LiteLLM telepítése OKE-re Cloud Shellből

Minden parancsot az **OCI Console Cloud Shell termináljában** futtass. A saját gépeden csak böngésző kell. A kész nyilvános OCIR-képeket az OKE worker node-ok töltik le: a Cloud Shell tárhelyére csak a repo, a konfiguráció és néhány kis fájl kerül.

Az OCI CLI beállítja az OKE-hozzáférést. Ezután a csomag telepítőscriptje kubectl-lel telepít egy Streamlit- és egy LiteLLM-podot. A böngésző a meglévő Load Balanceren keresztül éri el az appot; a LiteLLM a saját OCI PostgreSQL 16 adatbázisodat és az OCI Generative AI szolgáltatást használja.

A meglévő infrastruktúrát és az adminisztrátori hozzáférést adottnak vesszük. A számozott pontokon sorban haladj; hibánál állj meg az adott pontnál. A `REPLACE_...` értékeket cseréld a sajátodra. A p01 ismert adatai: [P01.hu.md](P01.hu.md).

## 1 Cloud Shell megnyitása és az OCI CLI ellenőrzése

1. Jelentkezz be az **OCI Console**-ba, és válaszd ki a cluster régióját, például **Germany Central (Frankfurt)**.
2. Jobbra fent **Developer tools / terminál ikon → Cloud Shell**.
3. A Cloud Shell felső **Network** menüjében válaszd a **Public Network** lehetőséget. A fő útvonal publikus OKE API-végpontot használ. Privát végponthoz a 3. pont külön változatát kövesd.
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

## 3 Az OKE-kapcsolat beállítása OCI CLI-vel

**OCI Console → Kubernetes Engine → Clusters → saját cluster → Actions → Access cluster → Cloud Shell Access.** Innen másold ki a cluster OCID-ját. A következő blokk első két sorát töltsd ki, majd futtasd Cloud Shellben:

```bash
WORKSHOP_CLUSTER_OCID='REPLACE_CLUSTER_OCID'
WORKSHOP_CLUSTER_REGION='eu-frankfurt-1'
umask 077
mkdir -p "$HOME/.kube"
chmod 700 "$HOME/.kube"
export KUBECONFIG="$HOME/.kube/oci-ai-workshop.config"
oci ce cluster create-kubeconfig --cluster-id "$WORKSHOP_CLUSTER_OCID" --file "$KUBECONFIG" --region "$WORKSHOP_CLUSTER_REGION" --token-version 2.0.0 --kube-endpoint PUBLIC_ENDPOINT
chmod 600 "$KUBECONFIG"
kubectl config current-context
kubectl get nodes --request-timeout=10s -L kubernetes.io/arch,node.kubernetes.io/instance-type
```

**Elvárt:** saját context és legalább egy **Ready / amd64** worker. A context értékét a következő pontban fogod használni. A Cloud Shell lehet ARM vagy AMD gép; a kiadott képekhez a **worker node** legyen AMD64. A kubectl minor verziója legfeljebb eggyel térjen el a clusterétől; a p01 v1.37.1-hez a korábban látott v1.36.4 kliens megfelelő. [OKE-hozzáférés](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengdownloadkubeconfigfile.htm)

**Ha timeoutot kapsz:** a Public Network kiválasztása önmagában nem nyitja meg az OKE API portját. Cloud Shellben `curl -4 -fsS https://checkip.amazonaws.com`; a kapott kilépő IPv4-címet engedd az API-végpont NSG-jében: **Add ingress rule → Stateful → Source type CIDR → cím/32 → TCP → Source port All → Destination port 6443**. NSG hiányában az API subnet security listjében legyen meg a szabály. Ez a Cloud Shell címe, nem a laptopodé; új sessionben változhat. Ismételd meg a `kubectl get nodes` parancsot.

**Ha csak privát API-végpont van:** a repo letöltése után válaszd a Cloud Shell **Network → Private Network Definition List → Create Private Network Definition** menüt, a clusterhez hálózati úttal rendelkező VCN-t/subnetet, majd **Use as active network → Create**. A session régiója egyezzen a subnetével. Engedd a Cloud Shell privát subnetjéből a TCP/6443-at az OKE API-hoz. A fenti parancsban `PUBLIC_ENDPOINT` helyett `PRIVATE_ENDPOINT` szerepeljen. A további GitHub-eléréshez ezen a hálózaton internetkimenet is kell. [Cloud Shell hálózat](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/cloudshellintro_topic-Cloud_Shell_Networking.htm)

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

Az infrastruktúrában ezek a kapcsolatok működjenek:

| Forrás → cél | Port |
| --- | --- |
| OKE worker node → OCIR | TCP/443 |
| OKE pod → OCI Generative AI | TCP/443 |
| LiteLLM és DB-előkészítő pod → PostgreSQL | TCP/5432, illetve a saját `DB_PORT` |

A DB NSG-jében a cluster CNI/SNAT szerinti **worker/pod forrást** engedélyezd. A régi LiteLLM VM engedélye nem elég. A DB-kapcsolatot a clusterben futó Job teszteli; a Cloud Shellnek nem kell közvetlen PostgreSQL-elérés. Részletes hálózati beállítások: [UZEMELTETES.hu.md](UZEMELTETES.hu.md).

Cloud Shellben:

```bash
python3 tools/workshop.py check
python3 tools/workshop.py prepare
```

A `prepare` rejtve, kétszer kéri az **alkalmazás DB-felhasználójának jelszavát**. Új `litellm_k8s` userhez válassz új jelszót; meglévő usernél annak jelenlegi jelszavát add meg. A program ellenőrzi az API-kulcs fingerprintjét és a CA-t, majd létrehozza a namespace-t és a szükséges Kubernetes Secreteket/ConfigMapeket. A hitelesítőket a védett `local` könyvtárban is megőrzi; újrafuttatáskor nem cseréli le őket.

**Ha még nincs külön alkalmazás-DB és user:**

```bash
python3 tools/workshop.py init-db
```

Ez a `DB_ADMIN` **PostgreSQL-jelszavát** kéri rejtve. A Job csak a hiányzó DB-t és felhasználót hozza létre, az alkalmazásfelhasználót teszi DB-tulajdonossá, és kezeli az ehhez szükséges átmeneti `SET ROLE` jogot. Meglévő DB-t/jelszót nem ír felül. A futás végén törli az átmeneti admin Secretet és Jobot.

**Akár új, akár meglévő a DB, ezután kötelező:**

```bash
python3 tools/workshop.py prepare-db
kubectl -n oci-ai-k8s logs job/db-check-db
```

**Elvárt:** `PASS: alkalmazas DB-kapcsolat, PostgreSQL 16, verify-full TLS es schema CREATE jog.` Csak ezután folytasd. A Job az alkalmazásfelhasználóval tesztel, FQDN- és CA-ellenőrzéssel. A LiteLLM táblái a következő pontban készülnek el.

Az első DB-Job indításakor az OKE már automatikusan letölti a LiteLLM-képet az OCIR-ből. Ha más `NAMESPACE` értéket választottál, a kézi `kubectl -n oci-ai-k8s` parancsokban is azt használd.

## 7 A LiteLLM és a Streamlit telepítése

```bash
bash scripts/install.sh
python3 tools/workshop.py status
```

A script sorrendben ellenőrzi a DB-t, lefuttatja a LiteLLM migrációs Jobot, elindítja a LiteLLM-et, létrehozza az app korlátozott virtuális kulcsát, majd elindítja a Streamlitet és ellenőrzi a kapcsolatukat. A virtuális kulcs az `oci-cohere` modellhez használható, 10 USD kerettel és 10 kérés/perc limittel.

**Elvárt:** `PASS: a Kubernetes alkalmazasok keszek.` A `litellm` és `streamlit` egy-egy Ready poddal fut. A LiteLLM Service `ClusterIP`, a Streamlité `NodePort`. A befejezett Jobok `Completed` állapota rendben van.

A Kubernetes közvetlenül a nyilvános OCIR-ből tölti le a két rögzített kiadást a worker node-okra. Cloud Shellben nincs több GB-os kép vagy konténerfuttatás. Ez a teszt még nem hívja a fizetős GenAI-modellt.

Ha már fut korábbi LiteLLM deployment, az újratelepítés előtt az [üzemeltetési leírás](UZEMELTETES.hu.md) frissítési lépéseit kövesd; a script élő kiszolgáló mellett nem indít migrációt.

## 8 A meglévő Load Balancer bekötése

Cloud Shellben kérd le az aktuális worker címeket:

```bash
kubectl get nodes -o wide
```

**OCI Console → Networking → Load Balancers → saját meglévő LB.**

1. **Backend sets → Create backend set**: név `oci-ai-k8s-backends`, policy **Round robin**.
2. Health check: **HTTP**, port **30080**, path **`/_stcore/health`**, status **200**.
3. **Backends → Add backends → IP addresses**: add hozzá minden használható worker **INTERNAL-IP** címét, port **30080**. A worker címét használd, ne a pod vagy a Service IP-jét.
4. Engedd az **LB → worker TCP/30080** forgalmat: worker ingress forrása az LB NSG-je (**Source type NSG**), vagy NSG hiányában az LB subnet CIDR-je (**Source type CIDR**). Az LB-n az egress is legyen engedett. Több LB-subnetnél mindet vedd figyelembe.
5. Várd meg a backendek **Healthy** állapotát.
6. **Listeners → Create listener**: név `oci-ai-k8s-http`, protocol **HTTP**, port **8080**, default backend set `oci-ai-k8s-backends`, idle timeout **300 másodperc**. A port egyezzen a `settings.env` `APP_PUBLIC_PORT` értékével. A meglévő VM-es HTTP/80 listenert hagyd meg; szabad, kifejezetten ennek az appnak adott 80-as port is használható.
7. Az LB NSG-jében, vagy NSG hiányában a subnet security listjében: stateful ingress, **Source type CIDR**, a böngészőt használó résztvevői hálózat/cím, **TCP**, source port **All**, destination port **8080**.

Más `NODE_PORT` értéknél a 30080-at mindenhol cseréld arra. A p01 LB-n nincs NSG, ott a subnet security listjével kell számolni. A Streamlit WebSocket-kapcsolatát a köztes proxyk is engedjék. [OCI LB listenerek](https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managinglisteners.htm)

Privát LB esetén a böngészőt futtató gépnek hálózati elérés kell az LB-hez.

Egy app-pod mellett is lehet több worker backend, mert a Service cluster-szinten továbbít. A kézi backendlista nem követi a worker IP-cseréjét; ilyenkor frissítsd.

## 9 Böngészős próba és az adatbázis naplójának ellenőrzése

1. A saját géped böngészőjében nyisd meg: **`http://REPLACE_LB_ADDRESS:8080`**. A p01 jelenlegi címe: **`http://92.5.181.255:8080`**. Meglévő HTTPS listener esetén annak címét használd.
2. A chatmezőben küldj egy rövid kérdést: `Válaszolj egy szóval: működik?`
3. Ellenőrizd a választ, a tokenhasználatot és a becsült költséget.

Ez **fizetős OCI GenAI-hívás**. A megjelenő költség a `proxy/config.yaml` demóáraiból számított becslés. Az OCI-kulcs, DB-jelszó és LiteLLM master key a böngészőhöz nem kerül.

Ha egy konkrét kérés PostgreSQL naplósorát is ellenőriznéd, Cloud Shellben indíts egy **külön, fizetős** tesztkérést:

```bash
python3 tools/workshop.py smoke
python3 tools/workshop.py verify-spend
```

**Elvárt:** modellválasz és call ID, majd ugyanahhoz a call ID-hoz pozitív spend sor a DB-ben. Ha a sor még nem látszik, várj egy percet, és **csak a `verify-spend` parancsot ismételd**. Ez nem küld új modellkérést.

## 10 Folytatás új Cloud Shell sessionből

Nyisd meg ugyanazzal az OCI-felhasználóval és ugyanabban a Cloud Shell régióban. Válaszd a 3. pontban működő hálózatot, majd:

```bash
cd ~/ocitestdrivebudapest/KubernetesApplications
export KUBECONFIG="$HOME/.kube/oci-ai-workshop.config"
kubectl config current-context
kubectl get nodes --request-timeout=10s
```

A context egyezzen a `settings.env` értékével. Folytasd az utolsó sikeres pont után; őrizd meg a meglévő `settings.env` és `local` fájlokat. A `local` hitelesítőiről legyen védett mentésed. Sessionbontás után az OKE-n futó appok tovább működnek.

Frissítés, hibaelhárítás, hálózati részletek és eltávolítás: [UZEMELTETES.hu.md](UZEMELTETES.hu.md).
