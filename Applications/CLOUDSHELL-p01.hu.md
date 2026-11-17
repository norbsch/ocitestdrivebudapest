# A p01 környezet adatai a Cloud Shell telepítéshez

A telepítést a [GUIDE.hu.md](GUIDE.hu.md) fejezetein végezd sorban. Ebben a környezetben **a két jelenlegi VM csak a Streamlit appot futtatja**, és külön harmadik VM szolgálja ki őket LiteLLM-mel. A Cloud Shellből közvetlen privát SSH-val kapcsolódsz mindhárom VM-re.

| Mező | Érték |
| --- | --- |
| Infrastruktúra régiója | Germany Central (Frankfurt), `eu-frankfurt-1` |
| Compartment | `OCITestDriveBudapest` |
| VCN | `p01-vcn` |
| Cloud Shellhez választandó privát subnet | `p01-subnet-private-vm` |
| app-01 privát IP | `10.0.1.2` |
| app-02 privát IP | `10.0.1.3` |
| Külön LiteLLM VM privát IP | **Még nem ismert; a VM létrehozásakor kitöltendő** |
| Appok backend portja | HTTP/80 mindkét app VM-en |
| LiteLLM portja | HTTP/4000 a privát hálózaton |
| Meglévő SSH-kulcs feltöltendő fájlneve | `p01-vm-key` |
| A kulcs helye importálás után a Cloud Shellben | `~/.ssh/oci-ai-workshop` |
| SSH-felhasználó | `ubuntu`, Ubuntu VM-eket feltételezve |

A LiteLLM-hez ne a `10.0.1.2` vagy `10.0.1.3` címet használd: mindkettő app VM. A fő guide 5. fejezetének LiteLLM-belépési próbáját csak az új VM címe és hozzáférése birtokában lehet elvégezni. Addig a guide adatgyűjtési, kulcs- és app-előkészítési része végezhető el; a teljes telepítéshez kell a harmadik VM.

## 1 Cloud Shell és az SSH-kulcs

**CONSOLE:** Frankfurt régió → Cloud Shell / Code Editor ikon → Cloud Shell. A Cloud Shell tényleges régiója is Frankfurt legyen; eltérő home régiónál a regional launch lehetőséggel indítsd itt.

A fő guide bevezető előkészítése után a 2.1 pontban az **Upload** menüvel a saját géped `/Users/gepeter/Downloads/p01-vm-key` fájlját válaszd ki. A feltöltés után a Cloud Shellben a `~/p01-vm-key` forrásnévvel futtasd az importálást. A helyi `/Users/gepeter/...` útvonalat ne írd Cloud Shell-parancsba.

A meglévő appokhoz a meglévő kulcsot importáld. Az új LiteLLM VM létrehozásakor az infrastruktúra gazdája ugyanennek a kulcsnak a publikus párját engedélyezze az `ubuntu` felhasználónál, vagy biztosítson hozzá külön kulcsot; utóbbi esetben a LiteLLM SSH-blokkjában annak privát útvonalát használd.

A workshop résztvevői a saját kulcsukat és saját környezetük címeit használják.

## Repository a Cloud Shellben

A fő guide 3. fejezete szerint klónozd a `norbsch/ocitestdrivebudapest` repót. Az alkalmazások forrása a Cloud Shellben: `~/ocitestdrivebudapest/Applications`.

GitHubhoz Public Network vagy interneteléréssel rendelkező privát hálózat kell. A VM-ek SSH-eléréséhez utána a `p01-private-network` hálózati definíció legyen aktív. A fő guide 5.4 pontja az `Applications` tartalmát a VM-ek `/home/ubuntu/oci-ai-workshop` könyvtárába másolja.

## 2 Hálózati elérések

A fő guide 4. fejezetében a `p01-vcn` VCN-hez tartozó `workshop-cloudshell-nsg` csoportot vagy az infrastruktúra gazdájától kapott megfelelő NSG-t válaszd.

| Forgalom | Engedély |
| --- | --- |
| Cloud Shell privát VNIC → mindhárom VM | TCP/22; forrás a Cloud Shell NSG-je |
| LB → app-01 `10.0.1.2` | HTTP/80; forrás az LB NSG-je |
| LB → app-02 `10.0.1.3` | HTTP/80; forrás az LB NSG-je |
| app-01 `10.0.1.2/32` → LiteLLM | TCP/4000 |
| app-02 `10.0.1.3/32` → LiteLLM | TCP/4000 |
| LiteLLM → menedzselt PostgreSQL | TCP/5432, TLS |
| LiteLLM → OCI Generative AI | HTTPS/443 |

Az NSG-k kimenő szabályai és a VM-ek helyi tűzfalai is engedjék a megfelelő forgalmat. A VM-ek csomagletöltéséhez külön kimenő internet/csomagtükör szükséges. A VM-ekhez ténylegesen hozzárendelt NSG-ket válaszd ki a primary VNIC adataiból; a neveiket nem olvastuk ki a környezetből.

## 3 Cloud Shell Private Network Access

A fő guide 5.1 pontjában:

| Mező | Érték |
| --- | --- |
| Network | Private Network Definition List |
| Name | `p01-private-network` |
| Compartment | `OCITestDriveBudapest` |
| VCN | `p01-vcn` |
| Subnet | `p01-subnet-private-vm` |
| Network Security Groups | a Cloud Shellhez előkészített NSG |
| Use as active network | bekapcsolva |

**Create**, majd várd meg a csatlakozást. A Network mező a `p01-private-network` definíciót mutassa. Az új LiteLLM VM lehet másik elérhető subnetben is, de a Cloud Shellből és mindkét appból legyen hozzá útvonal és megfelelő hálózati engedély.

## 4 Konkrét SSH konfiguráció

A fő guide 5.2 pontjában a Cloud Shell `~/.ssh/config` fájljában a LiteLLM helyőrzőjét az új VM valódi privát IP-jével kell majd kitölteni:

```sshconfig
Host td-litellm
    HostName REPLACE_LITELLM_PRIVATE_IP
    Port 22
    User ubuntu
    IdentityFile ~/.ssh/oci-ai-workshop
    IdentitiesOnly yes
    ServerAliveInterval 60

Host td-app-01
    HostName 10.0.1.2
    Port 22
    User ubuntu
    IdentityFile ~/.ssh/oci-ai-workshop
    IdentitiesOnly yes
    ServerAliveInterval 60

Host td-app-02
    HostName 10.0.1.3
    Port 22
    User ubuntu
    IdentityFile ~/.ssh/oci-ai-workshop
    IdentitiesOnly yes
    ServerAliveInterval 60
```

A régi `td-app` blokkot és a régi IP-re mutató `td-litellm` blokkot cseréld le. Ne maradjanak azonos nevű blokkok többször.

A LiteLLM-cím kitöltése után a fő guide 5.3 pontja szerint teszteld mindhárom SSH-belépést, majd másold fel a csomagot mindhárom VM-re. A meglévő két app SSH-elérését már előbb is ellenőrizheted.

## 5 Az alkalmazások beállításai

A LiteLLM VM-en a fő guide 6. fejezetének `deployment.env` fájljában:

```dotenv
LITELLM_PRIVATE_IP=REPLACE_LITELLM_PRIVATE_IP
APP_01_PRIVATE_IP=10.0.1.2
APP_02_PRIVATE_IP=10.0.1.3
```

A LiteLLM-helyőrzőt a tényleges harmadik VM címére cseréld. A két app a 13. fejezetben ugyanazt a LiteLLM URL-t és virtuális kulcsot kapja. Az OCI API-kulcs és a DB-jelszó csak a LiteLLM VM-re kerül.

A külön LiteLLM VM-re belépve, az adatlap és kulcsok előkészítése után előbb a fő guide 7.5 pontjának `bash scripts/prepare_postgres.sh` parancsát futtasd. Ez létrehozza és teszteli a PostgreSQL alkalmazás-adatbázist és felhasználót. A 8. pont sikeres kapcsolatellenőrzése után a 9. fejezet `bash scripts/install_litellm.sh` parancsa végzi egyben a telepítést. Mindkét app VM-en a 14. fejezet `bash scripts/install_app.sh` parancsát használd a közös appkonfiguráció felmásolása után. A mellékelt service a **80-as porton**, `ubuntu` felhasználóként indul, a szükséges portkötési capabilityvel.

## 6 Az LB beállításai és tesztje

A meglévő LB app-backend setjében a fő guide 16. fejezete szerint:

- Backend 1: `10.0.1.2:80`.
- Backend 2: `10.0.1.3:80`.
- HTTP health check: port `80`, útvonal `/_stcore/health`, elvárt kód `200`.
- Listener: HTTP/80, ehhez a közös backend sethez irányítva.
- Round robin, load balancer cookie persistence és engedélyezett fallback.

A LiteLLM harmadik VM-je nem kerül az LB app-backend setjébe. Mindkét app magán az app VM-en futó Python-kliensből hívja hátra a LiteLLM-et, a LiteLLM pedig az OCI GenAI-t.

A böngészőben a tényleges LB URL-jét nyisd meg. Privát LB-hez a saját gépednek külön privát hálózati út kell; a Cloud Shell privát elérése ezt nem biztosítja a böngésződnek. A fő guide 16.3 pontja külön teszteli, hogy bármelyik app leállása után a másik kiszolgál.

A PostgreSQL primary FQDN, CA, adminfelhasználó, GenAI régió/compartment és LB URL az aktuális tesztkörnyezetből szükséges. A korábbi demó értékeit ne másold át automatikusan.

A dokumentáció készítésekor nem történt infrastruktúra-módosítás vagy élő telepítési teszt.
