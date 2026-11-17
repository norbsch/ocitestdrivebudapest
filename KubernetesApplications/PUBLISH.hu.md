# Workshop-képek készítése Cloud Shellből és publikálása OCIR-be

Ezt az oktató végzi el egyszer. A két kész Linux/AMD64 képet Public OCIR repositorykban adjuk ki. A résztvevők a [GUIDE.hu.md](GUIDE.hu.md) alapján telepítenek: nem buildelnek, és nincs szükségük registry-tokenre.

A képek alkalmazáskódot tartalmaznak. A DB-jelszót, OCI privát kulcsot és a résztvevői konfigurációt telepítéskor adjuk meg. Ez az útmutató nem telepít a clusterre és nem módosít adatbázist.

## 1 Cloud Shell és forráskód

OCI Console → Cloud Shell. Válassz **X86_64** architektúrát és a külső letöltéseket elérő hálózatot. Ehhez a buildhez a Public Network használható; a későbbi clustertelepítéshez szükséges privát hálózatra vissza lehet váltani.

Ha még nincs klón:

```bash
git clone https://github.com/norbsch/ocitestdrivebudapest.git
```

Meglévő klónnál:

```bash
cd ~/ocitestdrivebudapest
git pull --ff-only origin main
```

```bash
cd ~/ocitestdrivebudapest/KubernetesApplications
uname -m
command -v podman
command -v skopeo
command -v fuse-overlayfs
df -h /tmp
```

**Elvárt:** `x86_64`, mindhárom eszköz elérési útja és több GiB szabad hely a `/tmp` fájlrendszeren. A most tesztelt környezetben 4,6 GB szabad hely volt; a teljes LiteLLM-build beleférését még élőben ellenőrizni kell. Helyhiánynál állj meg és őrizd meg a hibakimenetet.

## 2 Elkülönített Podman-tárhely

Minden új Cloud Shell munkamenetben, ugyanabban a terminálban futtasd:

```bash
umask 077
export WORKSHOP_BUILD_ROOT="$(mktemp -d /tmp/oci-ai-k8s.XXXXXX)"
mkdir -p "$WORKSHOP_BUILD_ROOT"/{storage,run,tmp}
python3 tools/publish.py check
```

**Elvárt:** `PASS: elkulonitett AMD64 Podman tarhely: /tmp/oci-ai-k8s.…/storage`.

Ha már létrehoztad és tesztelted a `WORKSHOP_BUILD_ROOT` változót ebben a terminálban, az új könyvtár létrehozása helyett elég:

```bash
export WORKSHOP_BUILD_ROOT
python3 tools/publish.py check
```

A script minden Podman-parancsnak megadja a külön `--root`, `--runroot`, `overlay` és `fuse-overlayfs` beállítást, valamint a letöltési ideiglenes könyvtárat. A home alatti régi képtárat nem használja. Ne helyettesítsd a scriptet sima `podman` build/prune parancsokkal. A `/tmp` átmeneti: Cloud Shell újraindításakor új tárhelyet kell létrehozni. [Podman tárhelybeállítások](https://docs.podman.io/en/latest/markdown/podman.1.html)

## 3 Két Public OCIR repository

**OCI Console → Frankfurt → Container Registry → oktatói compartment → Create repository.**

1. Repository type: **Standard**.
2. Repository name: **`oci-ai-k8s-streamlit`**.
3. Access: **Public**.
4. **Create**.
5. Ismételd meg **`oci-ai-k8s-litellm`** névvel, szintén Public hozzáféréssel.

Meglévő repositorynál ellenőrizd a Public hozzáférést. A script nem állítja át a láthatóságot. A jóváhagyott célok: `fra.ocir.io/frgmw9rkvlkd/oci-ai-k8s-streamlit` és `fra.ocir.io/frgmw9rkvlkd/oci-ai-k8s-litellm`. [OCI repository létrehozás](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrycreatingarepository.htm)

## 4 Publikáló konfiguráció és Auth Token

A Cloud Shellben, a `KubernetesApplications` könyvtárban:

```bash
test -f publish.env || cp templates/publish.env.example publish.env
chmod 600 publish.env
nano publish.env
```

| Mező | Érték |
| --- | --- |
| `REGISTRY` | `fra.ocir.io` |
| `OCIR_NAMESPACE` | `frgmw9rkvlkd` |
| `OCIR_USERNAME` | Saját OCI-felhasználónév, szükség esetén domainnel, például `Default/user@example.com`; tenancy namespace nélkül |
| `APP_REPOSITORY` | `oci-ai-k8s-streamlit` |
| `PROXY_REPOSITORY` | `oci-ai-k8s-litellm` |
| `IMAGE_TAG` | Első kiadáskor `workshop-v1`; kódváltoztatás után új verzió |
| `IMAGE_PULL_AUTH` | `public` |

Ne legyen idézőjel vagy `REPLACE` helyőrző. A fájlba nem kell jelszó, token, API-kulcs vagy DB-adat. A résztvevői `settings.env` nem szükséges a buildhez.

**OCI Console → Profil → My profile / User settings → Auth tokens → Generate token.** Név például `oci-ai-workshop-publish`. A tokent mentsd jelszókezelőbe; a következő parancs rejtett bekérésénél fogod megadni. Ez OCI Auth Token, nem a Console-jelszó.

## 5 Build → teszt → push, képenként

```bash
python3 tools/publish.py build-push
```

A script rejtve kéri a tokent, és szabványos bemeneten adja át a Podman-loginnak. A hitelesítés külön `local/publisher-auth.json` fájlba kerül, 0600 jogosultsággal; a script befejezéskor vagy kezelt hibánál eltávolítja. A `local/` nincs Gitben. Kényszerített leállítás után kézzel távolítsd el ezt az authfájlt.

A script sorrendje:

1. Streamlit Linux/AMD64 build, majd importpróba hálózat és credentialök nélkül.
2. Streamlit feltöltése; a registry digest és az anonim Linux/AMD64 elérés ellenőrzése.
3. A már feltöltött kép és buildadatainak törlése **kizárólag az elkülönített ideiglenes képtárból**.
4. LiteLLM build, importpróba, feltöltés és anonim ellenőrzés, ugyanilyen takarítással.
5. Csak mindkét kép sikere után frissül az `images.env` és annak `SHA256SUMS` bejegyzése.

A proxyban a Prisma-kliens build közben készül el. Az importpróba nem helyettesíti a későbbi élő PostgreSQL/GenAI-tesztet. A `skopeo inspect --no-creds` ellenőrzés kifejezetten anonim, ezért a publikáló bejelentkezése nem fedheti el a Private repositoryt. [Skopeo inspect](https://github.com/containers/skopeo/blob/main/docs/skopeo-inspect.1.md), [Podman push digestfile](https://docs.podman.io/en/v4.9.3/markdown/podman-push.1.html)

**Elvárt végső üzenet:** `PASS: mindket kep az OCIR-ben; images.env es SHA256SUMS frissitve.`

Hibánál az `images.env` előző tartalma megmarad. Az első kép közben már lehet az OCIR-ben. Ne add ki a félkész csomagot. A hiba javítása után a `build-push` újra az első képtől indul; ha a második build félbemaradt adatai miatt nincs hely, az alábbi paranccsal ürítsd csak ezt az ideiglenes képtárat, majd indítsd újra:

```bash
TMPDIR="$WORKSHOP_BUILD_ROOT/tmp" podman --root "$WORKSHOP_BUILD_ROOT/storage" --runroot "$WORKSHOP_BUILD_ROOT/run" --storage-driver=overlay --storage-opt=overlay.mount_program=/usr/bin/fuse-overlayfs image prune -a -f
```

Ez a takarítás csak akkor futtatható, ha nincs folyamatban build, és a `WORKSHOP_BUILD_ROOT` továbbra is a 2. pontban létrehozott saját `/tmp/oci-ai-k8s.*` könyvtár. Az alapértelmezett Podman-tárhelyet nem kell megjavítani a workshop buildjéhez.

## 6 Kiadási fájlok vissza a Git-repóba

```bash
cat images.env
git diff -- images.env SHA256SUMS
```

Az `images.env` két tényleges `@sha256:…` képcímet és `IMAGE_PULL_AUTH=public` értéket tartalmazzon. Amíg helyőrzős, nem használható résztvevői telepítéshez.

Cloud Shellből töltsd le az `images.env` és `SHA256SUMS` fájlokat a Cloud Shell **Download** funkciójával, és a saját Macen másold a klón `KubernetesApplications/` könyvtárába, a megfelelő fájlok helyére. Így a Git-push továbbra is a már beállított saját gépedről történik. A Macen a repo gyökeréből:

```bash
git add KubernetesApplications/images.env KubernetesApplications/SHA256SUMS
git --no-pager diff --cached --stat
git --no-pager diff --cached --name-only
git commit -m "Publish prebuilt OKE workshop image references"
git pull --rebase origin main
git push origin main
```

Konfliktusnál állj meg. Hitelesítőt és `local/` tartalmat ne tölts le a kiadáshoz és ne adj Githez.

## 7 Résztvevők és következő kiadás

A résztvevő a [GUIDE.hu.md](GUIDE.hu.md) szerint klónoz/frissít, átveszi a kész képhivatkozásokat, majd beállítja a saját DB- és OCI-hitelesítőit. A képeket az OKE node-ok töltik le az OCIR-ből.

Új kódhoz emeld az `IMAGE_TAG` értékét és ismételd a build/push/kiadási lépéseket. LiteLLM-verzió- és sémaváltozásnál a DB-mentés/migráció szabályai továbbra is érvényesek. A résztvevők által használt régi digesteket őrizd meg a registryben, hogy a podok később is újraindulhassanak.
