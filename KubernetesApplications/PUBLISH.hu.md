# Workshop-képek buildje külön OCI VM-en és publikálása OCIR-be

Ezt az oktató végzi el. A résztvevők a [GUIDE.hu.md](GUIDE.hu.md) alapján, OCI Cloud Shellből telepítenek, és a két kész Public OCIR-képet használják.

A LiteLLM-kép Cloud Shellben a végső mentésnél kifutott a rendelkezésre álló 4,6 GiB tárhelyből. A build ezért külön Linux/AMD64 VM-en fut. A korábbi `tools/publish.py` Cloud Shell-változat helyett itt a `tools/publish_vm.py` parancsot használjuk.

## 1 Build VM és eszközök

Ubuntu 24.04, AMD64; 2 OCPU, 16 GB RAM, 100 GB rendszerlemez. A VM érje el a GitHubot, a csomagtárakat, Docker Hubot és az OCIR-t. Az SSH 22-es portját a saját tényleges SSH-forráscímedre engedélyezd.

A saját gépedről, a megfelelő IP-címmel és kulcsútvonallal:

```bash
ssh -i /path/to/your-vm-key ubuntu@BUILD_VM_PUBLIC_IP
```

A VM-en telepítsd az eszközöket, ha még nincsenek fent:

```bash
sudo apt-get update
sudo apt-get install -y docker.io skopeo git python3 ca-certificates
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
exit
```

Lépj be újra ugyanazzal az SSH-paranccsal, hogy az új csoporttagság érvényesüljön:

```bash
docker version
skopeo --version
uname -m
df -h /
```

Elvárt: Docker Client és Server, működő Skopeo, `x86_64`, elegendő szabad tárhely. A VM `/var/lib/docker` könyvtárát használjuk; itt nincs Cloud Shell-féle 5 GB-os korlát.

## 2 Forráskód

A build VM-en, első alkalommal:

```bash
git clone https://github.com/norbsch/ocitestdrivebudapest.git
cd ocitestdrivebudapest/KubernetesApplications
```

Meglévő klón frissítésekor:

```bash
cd ~/ocitestdrivebudapest
git pull --ff-only origin main
cd KubernetesApplications
```

A 2026. november 17-én létrehozott build VM-en az előkészített csomag a `/opt/oci-ai-build/KubernetesApplications` könyvtárban van; azon a VM-en ezt használd:

```bash
cd /opt/oci-ai-build/KubernetesApplications
```

## 3 Public OCIR repositoryk

OCI Console → Frankfurt → Container Registry → a megfelelő compartment. Hozd létre vagy ellenőrizd:

| Repository | Access |
| --- | --- |
| `oci-ai-k8s-streamlit` | Public |
| `oci-ai-k8s-litellm` | Public |

Az elfogadott tenancy namespace: `frgmw9rkvlkd`, registry: `fra.ocir.io`. A script nem módosítja a láthatóságot. [Oracle repository létrehozás](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrycreatingarepository.htm)

## 4 Publikáló konfiguráció

A build VM-en, a csomag könyvtárában:

```bash
umask 077
test -f publish.env || cp templates/publish.env.example publish.env
chmod 600 publish.env
nano publish.env
```

```ini
REGISTRY=fra.ocir.io
OCIR_NAMESPACE=frgmw9rkvlkd
OCIR_USERNAME=REPLACE_IDENTITY_DOMAIN_AND_USERNAME
APP_REPOSITORY=oci-ai-k8s-streamlit
PROXY_REPOSITORY=oci-ai-k8s-litellm
IMAGE_TAG=workshop-v1
IMAGE_PULL_AUTH=public
```

OCI Console → profil ikon → My profile / User settings: nézd meg a pontos felhasználónevet és identity domaint. Ennél a környezetnél a tesztelt érték `Default/gergo.peter@oracle.com`. A saját felhasználódat add meg; a tenancy namespace-et a script teszi elé. A Cloud Shell Linux-neve nem a registry-felhasználónév.

Új képtartalom kiadásakor új verziózott tagot használj. A `publish.env` fájlba nem kerül token, jelszó vagy privát kulcs. A résztvevői `settings.env` nem kell a buildhez.

## 5 Build és ellenőrzés

```bash
python3 tools/publish_vm.py check
python3 tools/publish_vm.py build
```

Elvárt: `PASS: mindket kep elkeszult es az importproba sikeres.`

A script mindkét képet Linux/AMD64 platformra készíti, ellenőrzi az architektúrát, majd hálózat és OCI/DB-hitelesítők nélküli konténerekben importpróbát futtat. A LiteLLM-kép Prisma-kliensét is a build állítja elő. Ez nem helyettesíti a későbbi élő DB- és GenAI-tesztet.

## 6 Feltöltés és anonim ellenőrzés

OCI Console → My profile / User settings → Auth tokens → Generate token. Használhatod a saját meglévő Auth Tokenedet is. A token értékét csak a rejtett bekérésbe illeszd:

```bash
python3 tools/publish_vm.py push
```

A token beillesztésekor nem látszanak karakterek. Ez normális. A hitelesítés átmeneti, 0600 jogosultságú Docker-konfigurációba kerül, amelyet a script befejezéskor eltávolít. A token nem kerül a parancs argumentumába vagy Gitbe.

A script feltölti a képeket, és a `skopeo inspect --no-creds` paranccsal anonim módon ellenőrzi a kiadott digesteket és a Linux/AMD64 platformot. Csak mindkét kép sikere után frissíti az `images.env` és `SHA256SUMS` fájlokat. [Skopeo anonim ellenőrzés](https://github.com/containers/skopeo/blob/main/docs/skopeo-inspect.1.md)

Elvárt: `PASS: mindket kep az OCIR-ben; images.env es SHA256SUMS frissitve.`

Ha a feltöltés hibázik, a javítás után csak a `push` lépést kell ismételni; a kész helyi képek megmaradnak. A `build-push` paranccsal a két lépés egyben is futtatható.

## 7 Kiadási fájlok a Git-repóba

A build VM-en ellenőrizd:

```bash
cat images.env
```

Két `@sha256:…` képcímet és `IMAGE_PULL_AUTH=public` értéket kell látnod.

A saját gépeden, a repo gyökeréből másold le a két nem titkos kiadási fájlt. A parancsokban helyettesítsd a kulcsot, az IP-címet és szükség esetén a távoli csomag útvonalát:

```bash
scp -i /path/to/your-vm-key ubuntu@BUILD_VM_PUBLIC_IP:/opt/oci-ai-build/KubernetesApplications/images.env KubernetesApplications/images.env
scp -i /path/to/your-vm-key ubuntu@BUILD_VM_PUBLIC_IP:/opt/oci-ai-build/KubernetesApplications/SHA256SUMS KubernetesApplications/SHA256SUMS
```

A megfelelő forrásverzió legyen a helyi Git-klónban is, különben a SHA256SUMS más fájlverziókra fog hivatkozni. Ezután:

```bash
git add KubernetesApplications/
git --no-pager diff --cached --stat
git --no-pager diff --cached --name-only
```

A listában ne legyen `publish.env`, `settings.env`, `local/` vagy privát kulcs. Ellenőrzés után:

```bash
git commit -m "Publish prebuilt OKE workshop images and VM build guide"
git pull --rebase origin main
git push origin main
```

Konfliktusnál állj meg. A résztvevők ezután a [GUIDE.hu.md](GUIDE.hu.md) szerint telepítenek OCI Cloud Shellből. A podok a kész képeket közvetlenül az OCIR-ből töltik le.

## 8 Build VM a munka után

A kész képek az OCIR-ben maradnak, nem a build VM-ről töltődnek. Ha nincs több build, a VM leállítható; a rendszerlemezt és a forrásokat megtarthatod a következő kiadáshoz. Az OCI Console-ban a VM költségeit és a megmaradó boot volume-ot is vedd figyelembe.

Új kiadásnál emeld az `IMAGE_TAG` értékét, ismételd az 5–7. pontot, és őrizd meg a résztvevők által még használt régi digesteket a registryben.
