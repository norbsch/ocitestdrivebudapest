# OCI AI Kubernetes telepítőcsomag

Telepítés **OCI Cloud Shellből**, előre kiadott nyilvános OCIR-képekkel, meglévő AMD64 OKE clusterre. Egy Streamlit-pod és egy LiteLLM-pod indul; konfigurálható OCI PostgreSQL 16, OCI Generative AI és meglévő OCI Load Balancer kapcsolódik hozzájuk.

Kezdd itt: [GUIDE.hu.md](GUIDE.hu.md). A sorrend: Cloud Shell és OCI CLI ellenőrzése → repo klónozása → OKE-hozzáférés → saját beállítások és hitelesítők → DB-előkészítés → telepítőscript → LB → böngészős teszt.

A Cloud Shellben az OCI CLI és a kubectl előre telepített. A képeket közvetlenül az OKE tölti le az OCIR-ből a worker node-okra; a Cloud Shellben csak a kis telepítőcsomag és a konfiguráció marad. Résztvevőként registry-token és helyi konténerfuttató nem szükséges.

- [P01.hu.md](P01.hu.md): a p01 környezet ismert adatai.
- [UZEMELTETES.hu.md](UZEMELTETES.hu.md): hálózat, hibakeresés, frissítés és eltávolítás.
- `images.env`: a két kiadott kép rögzített digestes OCIR-címe.
- `templates/settings.env.example`: a környezeti beállítások sablonja.
- `tools/verify_package.py`: a csomag ellenőrzése.
- `tools/workshop.py`: hitelesítők, DB-előkészítés, telepítés és ellenőrzés.
- `scripts/install.sh`: LiteLLM és Streamlit telepítése előkészített DB-re.
- [ELLENORZES.txt](ELLENORZES.txt): az elvégzett és a még hátralévő ellenőrzések.

Repository-hely: `ocitestdrivebudapest/KubernetesApplications`. A csomag a VM-es Applications telepítőtől független. Tényleges jelszót, API-kulcsot, registry tokent vagy kubeconfigot nem tartalmaz.
