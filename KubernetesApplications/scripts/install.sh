#!/usr/bin/env bash
# Cloud Shell installer. Published images, settings, credentials and DB preparation precede this.
set -Eeuo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python3 tools/workshop.py check
python3 tools/workshop.py prepare-db
python3 tools/workshop.py deploy-litellm
python3 tools/workshop.py create-app-key
python3 tools/workshop.py deploy-app
python3 tools/workshop.py verify
printf '\nPASS: a Kubernetes alkalmazasok keszek. Az LB bekoteset a guide szerint vegezd el. Modellhivas nem tortent.\n'
