#!/bin/bash

printf '\033c\033[3J' 2>/dev/null || clear 2>/dev/null || true

set -e

CYAN='\e[1;36m'
GREEN='\e[1;32m'
YELLOW='\e[1;33m'
RED='\e[1;31m'
BOLD='\e[1m'
NC='\e[0m'

REPO_RAW="https://raw.githubusercontent.com/1NoJoom/T.Sin_Pro/main"
INSTALL_PATH="/usr/local/bin/T.Sin"
TMP_PATH="/tmp/T.Sin_Pro.py"

clear_screen() {
  printf '\033c\033[3J' 2>/dev/null || clear 2>/dev/null || printf '\033[2J\033[H'
}

show_banner() {
  echo -e "${CYAN}${BOLD}"
  echo "  ████████╗    ███████╗██╗███╗   ██╗"
  echo "  ╚══██╔══╝    ██╔════╝██║████╗  ██║"
  echo "     ██║       ███████╗██║██╔██╗ ██║"
  echo "     ██║       ╚════██║██║██║╚██╗██║"
  echo "     ██║  ██╗  ███████║██║██║ ╚████║"
  echo "     ╚═╝  ╚═╝  ╚══════╝╚═╝╚═╝  ╚═══╝"
  echo -e "${NC}${BOLD}         T.Sin Pro  ·  Installer${NC}"
  echo
}

banner() {
  clear_screen
  show_banner
}

if [ "$(id -u)" -ne 0 ]; then
  echo -e "${RED}[-] Please run as root (sudo).${NC}"
  exit 1
fi

show_banner
echo -e "${CYAN}[*] Installing T.Sin Pro...${NC}"

if ! command -v apt-get >/dev/null 2>&1; then
  echo -e "${RED}[-] This installer requires Ubuntu (apt).${NC}"
  exit 1
fi

echo -e "${YELLOW}[~] Updating packages & installing dependencies...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null 2>&1 || true
apt-get install -y python3 python3-pip curl wireguard wireguard-tools >/dev/null 2>&1 || true

banner
echo -e "${CYAN}[*] Installing T.Sin Pro...${NC}"
echo -e "${GREEN}[+] Dependencies ready${NC}"
echo -e "${YELLOW}[~] Installing Python packages...${NC}"
pip3 install --break-system-packages requests urllib3 >/dev/null 2>&1 || \
pip3 install requests urllib3 >/dev/null 2>&1 || true

banner
echo -e "${CYAN}[*] Installing T.Sin Pro...${NC}"
echo -e "${GREEN}[+] Dependencies ready${NC}"
echo -e "${GREEN}[+] Python packages ready${NC}"
echo -e "${YELLOW}[~] Downloading T.Sin Pro...${NC}"
if ! curl -fsSL "${REPO_RAW}/T.Sin.py?v=$(date +%s)" -o "${TMP_PATH}"; then
  echo -e "${RED}[-] Download failed. Make sure T.Sin.py is on the GitHub main branch.${NC}"
  exit 1
fi

if [ ! -s "${TMP_PATH}" ]; then
  echo -e "${RED}[-] Downloaded file is empty.${NC}"
  exit 1
fi

if ! head -n 1 "${TMP_PATH}" | grep -qiE '^#!.*python'; then
  printf '%s\n%s\n' '#!/usr/bin/env python3' "$(cat "${TMP_PATH}")" > "${TMP_PATH}.tmp"
  mv "${TMP_PATH}.tmp" "${TMP_PATH}"
fi

mv "${TMP_PATH}" "${INSTALL_PATH}"
chmod +x "${INSTALL_PATH}"

banner
echo -e "${GREEN}[+] Installed to ${INSTALL_PATH}${NC}"
echo -e "${GREEN}[+] Launch with: ${BOLD}T.Sin${NC}"
echo -e "${CYAN}[*] Starting T.Sin Pro...${NC}"
echo
sleep 1
clear_screen


if [ -r /dev/tty ]; then
  exec "${INSTALL_PATH}" </dev/tty >/dev/tty 2>/dev/tty
else
  exec "${INSTALL_PATH}"
fi
