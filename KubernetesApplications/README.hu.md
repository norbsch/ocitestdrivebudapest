# OCI AI Kubernetes telepítőcsomag

Különálló Cloud Shell telepítés meglévő AMD64 OKE-re: egy Streamlit pod, egy LiteLLM pod, konfigurálható külső PostgreSQL 16, OCI Generative AI és meglévő OCI Load Balancer NodePort-bekötéssel.

A teljes sorrend: [GUIDE.hu.md](GUIDE.hu.md). A p01 környezet már ellenőrzött adatai: [P01.hu.md](P01.hu.md).

- `app/Dockerfile`, `proxy/Dockerfile`: külön konténerképek, credentialök nélkül.
- `templates/settings.env.example`: a nem titkos környezeti beállítások sablonja.
- `proxy/config.yaml`: modellalias és árkonfiguráció.
- `tools/manifests.py`: a Kubernetes-erőforrások generátora, natív JSON formátumban.
- `tools/workshop.py`: OCIR-build/push, Secret-előkészítés, DB-Jobok, deploy, health és explicit modell/DB-tesztek.
- `runtime/`: a proxy-képben futó DB/TLS-, migrációs és adminsegédek.
- `scripts/install.sh`: dependency sorrendű telepítés, már előkészített DB-re, modellhívás nélkül.
- `tests/test_package.py`: offline ellenőrzések; futtatás: `python3 -m unittest discover -s tests -v`.
- [ELLENORZES.txt](ELLENORZES.txt): mi ellenőrzött helyben és mi vár élő tesztre.

Javasolt repository-hely: `ocitestdrivebudapest/KubernetesApplications`. A csomag nem igényli a VM-es `Applications` könyvtár jelenlétét. Tényleges jelszót, API-kulcsot, registry tokent és kubeconfigot a kiadás nem tartalmaz.
