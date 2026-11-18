#!/usr/bin/env bash
# Shared by VM preparation and installation scripts. No secret env file is evaluated as shell code.
set -Eeuo pipefail
umask 077
trap 'printf "HIBA: a telepites megallt (sor: %s). A javitas utan ujrafuttathato; titkos konfiguraciot nem general ujra.\n" "$LINENO" >&2' ERR
WORKSHOP_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
fail() { printf 'HIBA: %s\n' "$*" >&2; exit 1; }
step() { printf '\n== %s ==\n' "$*"; }
require_file() { [[ -s "$WORKSHOP_ROOT/$1" ]] || fail "Hianyzo vagy ures fajl: $1"; }
require_vm() {
    [[ "$(id -un)" == ubuntu && "$EUID" -ne 0 ]] || fail 'ubuntu felhasznalokent inditsd SSH utan, sudo nelkul.'
    [[ "$WORKSHOP_ROOT" == /home/ubuntu/oci-ai-workshop ]] || fail 'A csomag celja /home/ubuntu/oci-ai-workshop legyen.'
    # Ubuntu-supplied OS metadata; application env files are never sourced.
    . /etc/os-release
    [[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || fail 'Ubuntu 24.04 VM szukseges; Cloud Shellben ne futtasd.'
    [[ "$(dpkg --print-architecture)" == amd64 ]] || fail 'Ez a workshop amd64 VM-ekhez keszult.'
    sudo -n true
    cd "$WORKSHOP_ROOT"
}
check_port() {
    local port="$1" service="$2"
    if [[ -n "$(sudo ss -H -ltn "sport = :$port")" ]] && ! sudo systemctl is-active --quiet "$service"; then
        fail "A $port portot masik folyamat hasznalja. Egyeztess az oktatoval."
    fi
}
apt_install() {
    sudo apt-get update
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
}
allow_tcp() {
    local port="$1" source="${2:-}" rule=(-p tcp --dport "$1" -j ACCEPT)
    if [[ -n "$source" ]]; then rule=(-p tcp -s "$source/32" --dport "$port" -j ACCEPT); fi
    if ! sudo iptables -C INPUT "${rule[@]}" 2>/dev/null; then
        sudo iptables -I INPUT 1 "${rule[@]}"
    fi
}
install_unit() {
    local service="$1"
    sudo install -m 644 "templates/$service.service" "/etc/systemd/system/$service.service"
    sudo systemctl daemon-reload
    sudo systemctl enable "$service"
    sudo systemctl restart "$service"
}
