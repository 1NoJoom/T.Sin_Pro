# Sin Kabir on the Fucking T.Sin Pro Ver...
# T.Sin Pro v1.0.0
# Tel: @T_Sinn

import time
import os
import sys
import requests
import json
import subprocess
import re
import copy
import urllib3
import getpass
import urllib.request
import urllib.parse
import threading
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    _TZ_TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:
    _TZ_TEHRAN = timezone(timedelta(hours=3, minutes=30))


C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"
C_WHITE = "\033[97m"
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
DB_PATH = "/etc/x-ui/x-ui.db"
PG_TIMEOUT = 15
PG_SAVE_TIMEOUT = 30
PG_HOST_WAIT = 10
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
X3UI_CREDS_FILE = os.path.join(SCRIPT_DIR, ".3xui_relay_creds")
PG_CREDS_FILE = os.path.join(SCRIPT_DIR, ".pg_relay_creds")
X3UI_BINARY = "/usr/local/x-ui/x-ui"
X3UI_TOKEN_CACHE = os.path.join(SCRIPT_DIR, ".3xui_token_cache")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ThreeXUIClient:
    def __init__(self, base_url, username=None, password=None, api_token=None):
        self.base_url = base_url.rstrip('/')
        self.api_base_url = self.base_url[:-6] if self.base_url.endswith('/panel') else self.base_url
        self.username = username
        self.password = password
        self.api_token = api_token
        self.csrf_token = None
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        })
        if self.api_token:
            self.session.headers.update({"Authorization": f"Bearer {self.api_token}"})

    def _extract_csrf(self, html):
        m = re.search(r'name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']', html or "")
        return m.group(1) if m else None

    def _refresh_csrf(self):
        for path in ["/panel/", "/panel/inbounds", "/"]:
            try:
                r = self.session.get(f"{self.api_base_url}{path}", timeout=10)
                token = self._extract_csrf(r.text)
                if token:
                    self.csrf_token = token
                    self.session.headers.update({"X-CSRF-TOKEN": token})
                    return token
            except Exception:
                continue
        return None

    def login(self):
        if self.api_token:
            ok, err = self.test_connection()
            return ok, err
        if not self.username or not self.password:
            return False, "Missing username/password."
        try:
            r = self.session.get(f"{self.api_base_url}/", timeout=15)
            login_csrf = self._extract_csrf(r.text)
            headers = {"X-CSRF-TOKEN": login_csrf} if login_csrf else {}
            resp = self.session.post(
                f"{self.api_base_url}/login",
                data={"username": self.username, "password": self.password},
                headers=headers, timeout=15
            )
            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code}: {resp.text[:120]}"
            try:
                result = resp.json()
            except Exception:
                return False, f"Unexpected login response: {resp.text[:120]}"
            if not result.get("success"):
                return False, result.get("msg") or "Invalid username or password."
            self._refresh_csrf()
            return True, None
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to panel."
        except Exception as e:
            return False, str(e)

    def test_connection(self):
        url = f"{self.api_base_url}/panel/api/inbounds/list"
        last_error = ""
        for method in ["POST", "GET"]:
            try:
                r = self.session.post(url, timeout=10) if method == "POST" else self.session.get(url, timeout=10)
                if r.status_code == 200:
                    try:
                        result = r.json()
                        if result.get("success") or "obj" in result:
                            return True, None
                        last_error = f"Status 200 but success=False. Msg: {result.get('msg')}"
                    except Exception:
                        return True, None
                else:
                    last_error = f"HTTP {r.status_code}: {r.text[:100]}"
            except Exception as e:
                last_error = str(e)
        return False, last_error

    def get_inbounds(self):
        url = f"{self.api_base_url}/panel/api/inbounds/list"
        try:
            r = self.session.post(url, timeout=10)
            if r.status_code != 200:
                r = self.session.get(url, timeout=10)
            result = r.json()
            if r.status_code == 200 and result.get("success"):
                return True, result.get("obj", [])
            return False, []
        except Exception:
            return False, []

    def create_inbound(self, inbound_data):
        url = f"{self.api_base_url}/panel/api/inbounds/add"
        try:
            r = self.session.post(url, json=inbound_data, timeout=10)
            result = r.json()
            if r.status_code == 200 and result.get("success"):
                return True, result
            return False, result
        except Exception:
            return False, None

    def delete_inbound(self, inbound_id):
        url = f"{self.api_base_url}/panel/api/inbounds/del/{inbound_id}"
        try:
            r = self.session.post(url, timeout=10)
            result = r.json()
            return r.status_code == 200 and result.get("success")
        except Exception:
            return False

    def get_xray_setting(self):
        url = f"{self.api_base_url}/panel/api/xray/"
        try:
            r = self.session.post(url, timeout=10)
            result = r.json()
            if r.status_code == 200 and result.get("success"):
                return True, result.get("obj", {})
            return False, None
        except Exception:
            return False, None

    def update_xray_setting(self, xray_setting_str, outbound_test_url="https://www.google.com/generate_204"):
        url = f"{self.api_base_url}/panel/api/xray/update"
        try:
            r = self.session.post(url, data={"xraySetting": xray_setting_str, "outboundTestUrl": outbound_test_url}, timeout=10)
            result = r.json()
            return r.status_code == 200 and result.get("success")
        except Exception:
            return False

    def add_permanent_outbound(self, outbound_data):
        success, settings = self.get_xray_setting()
        if not success or not settings:
            return False
        try:
            if isinstance(settings, str):
                settings = json.loads(settings)
            xray_setting = settings.get("xraySetting", "{}")
            xray_config  = json.loads(xray_setting) if isinstance(xray_setting, str) else xray_setting
            xray_config.setdefault("outbounds", [])
            new_tag = outbound_data.get("tag")
            if new_tag:
                xray_config["outbounds"] = [ob for ob in xray_config["outbounds"] if ob.get("tag") != new_tag]
            xray_config["outbounds"].append(outbound_data)
            outbound_test_url = settings.get("outboundTestUrl", "https://www.google.com/generate_204")
            return self.update_xray_setting(json.dumps(xray_config, indent=2), outbound_test_url)
        except Exception:
            return False

    def add_routing_rule(self, rule_data):
        success, settings = self.get_xray_setting()
        if not success or not settings:
            return False
        try:
            if isinstance(settings, str):
                settings = json.loads(settings)
            xray_setting = settings.get("xraySetting", "{}")
            xray_config  = json.loads(xray_setting) if isinstance(xray_setting, str) else xray_setting
            xray_config.setdefault("routing", {}).setdefault("rules", [])
            new_inbound_tags = rule_data.get("inboundTag", [])
            xray_config["routing"]["rules"] = [
                r for r in xray_config["routing"]["rules"]
                if not any(tag in r.get("inboundTag", []) for tag in new_inbound_tags)
            ]
            xray_config["routing"]["rules"].append(rule_data)
            outbound_test_url = settings.get("outboundTestUrl", "https://www.google.com/generate_204")
            return self.update_xray_setting(json.dumps(xray_config, indent=2), outbound_test_url)
        except Exception:
            return False

    def delete_outbound_and_routing(self, outbound_tag, inbound_tag):
        success, settings = self.get_xray_setting()
        if not success or not settings:
            return False
        try:
            if isinstance(settings, str):
                settings = json.loads(settings)
            xray_setting = settings.get("xraySetting", "{}")
            xray_config  = json.loads(xray_setting) if isinstance(xray_setting, str) else xray_setting
            if "outbounds" in xray_config:
                xray_config["outbounds"] = [ob for ob in xray_config["outbounds"] if ob.get("tag") != outbound_tag]
            if "routing" in xray_config and "rules" in xray_config["routing"]:
                xray_config["routing"]["rules"] = [
                    r for r in xray_config["routing"]["rules"]
                    if inbound_tag not in r.get("inboundTag", []) and r.get("outboundTag") != outbound_tag
                ]
            outbound_test_url = settings.get("outboundTestUrl", "https://www.google.com/generate_204")
            return self.update_xray_setting(json.dumps(xray_config, indent=2), outbound_test_url)
        except Exception:
            return False

    def restart_xray_service(self):
        url = f"{self.api_base_url}/panel/api/server/restartXrayService"
        try:
            r = self.session.post(url, timeout=10)
            return r.status_code == 200 and r.json().get("success")
        except Exception:
            return False

class PasarGuardAPI:
    def __init__(self, base_url, username, password, core_id=1):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.core_id  = core_id
        self.token    = None
        self.headers  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    def login(self):
        url = f"{self.base_url}/api/admin/token"
        try:
            r = requests.post(url, data={"username": self.username, "password": self.password},
                              headers=self.headers, timeout=PG_TIMEOUT)
            if r.status_code == 200:
                data  = r.json()
                self.token = data.get("access_token")
                ttype = data.get("token_type", "Bearer")
                self.headers.update({
                    "Authorization": f"{ttype} {self.token}",
                    "Content-Type": "application/json"
                })
                return True
            elif r.status_code == 401:
                print(f"{C_RED}[-] Invalid username or password.{C_RESET}")
            else:
                print(f"{C_RED}[-] Login failed ({r.status_code}): {r.text}{C_RESET}")
            return False
        except requests.exceptions.ConnectionError:
            print(f"{C_RED}[-] Cannot connect to server.{C_RESET}")
            return False
        except Exception as e:
            print(f"{C_RED}[-] Error: {e}{C_RESET}")
            return False

    def get_core_config(self):
        url = f"{self.base_url}/api/core/{self.core_id}"
        try:
            r = requests.get(url, headers=self.headers, timeout=PG_TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                return data.get("config", data)
            print(f"{C_RED}[-] Error ({r.status_code}): {r.text}{C_RESET}")
            return None
        except requests.exceptions.Timeout:
            print(f"{C_RED}[-] Request timed out after {PG_TIMEOUT}s while fetching core config.{C_RESET}")
            return None
        except Exception as e:
            print(f"{C_RED}[-] Exception: {e}{C_RESET}")
            return None

    def save_core_config(self, config: dict, restart_nodes: bool = True):
        url     = f"{self.base_url}/api/core/{self.core_id}"
        params  = {"restart_nodes": str(restart_nodes).lower()}
        timeout = PG_SAVE_TIMEOUT if restart_nodes else PG_TIMEOUT
        try:
            r = requests.put(url, json={"config": config}, params=params,
                             headers=self.headers, timeout=timeout)
            if r.status_code in [200, 201]:
                if restart_nodes:
                    print(f"{C_GREEN}[+] Core config saved!{C_RESET}")
                return True
            print(f"{C_RED}[-] Save failed ({r.status_code}): {r.text}{C_RESET}")
            return False
        except requests.exceptions.Timeout:
            hint = " (xray restart may still be running on the panel — wait and check)" if restart_nodes else ""
            print(f"{C_RED}[-] Save timed out after {timeout}s{hint}.{C_RESET}")
            return False
        except Exception as e:
            print(f"{C_RED}[-] Exception: {e}{C_RESET}")
            return False

    def restart_core(self, quiet=False):
        url = f"{self.base_url}/api/core/{self.core_id}/restart"
        if not quiet:
            print(f"{C_YELLOW}[~] Restarting xray...{C_RESET}")
        try:
            r = requests.post(url, headers=self.headers, timeout=PG_SAVE_TIMEOUT)
            if r.status_code in (200, 201, 204):
                if not quiet:
                    print(f"{C_GREEN}[+] Xray restarted.{C_RESET}")
                return True
            if not quiet:
                print(f"{C_RED}[-] Restart failed ({r.status_code}): {r.text[:120]}{C_RESET}")
            return False
        except requests.exceptions.Timeout:
            if not quiet:
                print(f"{C_YELLOW}[!] Restart timed out — check the panel.{C_RESET}")
            return False
        except Exception as e:
            if not quiet:
                print(f"{C_RED}[-] Restart error: {e}{C_RESET}")
            return False

    def list_inbounds_raw(self):
        config = self.get_core_config()
        return config.get("inbounds", []) if config else []

    @staticmethod
    def _extract_outbound_endpoint(ob):
        settings = ob.get("settings", {}) or {}
        protocol = (ob.get("protocol") or "").lower()
        if "address" in settings and "port" in settings:
            return settings.get("address", "—"), str(settings.get("port", "?"))
        servers = settings.get("servers")
        if servers:
            return servers[0].get("address", "—"), str(servers[0].get("port", "?"))
        vnext = settings.get("vnext")
        if vnext:
            return vnext[0].get("address", "—"), str(vnext[0].get("port", "?"))
        peers = settings.get("peers")
        if peers:
            ep = peers[0].get("endpoint", "")
            if ":" in ep:
                addr, _, port = ep.rpartition(":")
                return addr, port
        if protocol in ("freedom", "blackhole", "dns", "loopback"):
            return "(direct)", "-"
        return "—", "?"

    def quick_remove_relay(self, inbound_tag: str):
        country = next((c for c in COUNTRIES if _pg_country_tag(c) == inbound_tag), None)
        if country:
            return pg_delete_countries_batch(self, [country]) > 0
        fake = {"flag": "", "name": inbound_tag, "in_port": -99999}
        return pg_delete_countries_batch(self, [fake]) > 0

    def get_hosts(self):
        url = f"{self.base_url}/api/hosts"
        try:
            r = requests.get(url, headers=self.headers, timeout=PG_TIMEOUT)
            if r.status_code == 200:
                return r.json()
            print(f"{C_RED}[-] Error fetching hosts ({r.status_code}): {r.text}{C_RESET}")
            return None
        except requests.exceptions.Timeout:
            print(f"{C_RED}[-] Request timed out after {PG_TIMEOUT}s while fetching hosts.{C_RESET}")
            return None
        except Exception as e:
            print(f"{C_RED}[-] Exception: {e}{C_RESET}")
            return None

    def save_hosts(self, hosts_data, quiet=False):
        url = f"{self.base_url}/api/hosts"
        try:
            r = requests.put(url, json=hosts_data, headers=self.headers, timeout=PG_TIMEOUT)
            if r.status_code in [200, 201]:
                if not quiet:
                    print(f"{C_GREEN}[+] Hosts saved!{C_RESET}")
                return True
            print(f"{C_RED}[-] Save hosts failed ({r.status_code}): {r.text}{C_RESET}")
            return False
        except Exception as e:
            print(f"{C_RED}[-] Exception: {e}{C_RESET}")
            return False
            
    def delete_host(self, host_id, quiet=False):
        url = f"{self.base_url}/api/host/{host_id}"
        try:
            r = requests.delete(url, headers=self.headers, timeout=PG_TIMEOUT)
            if r.status_code in [200, 204]:
                return True
            if not quiet:
                print(f"{C_RED}[-] Delete host failed ({r.status_code}): {r.text}{C_RESET}")
            return False
        except Exception as e:
            if not quiet:
                print(f"{C_RED}[-] Exception: {e}{C_RESET}")
            return False

    def bulk_delete_hosts(self, host_ids: list):
        if not host_ids:
            return True
        url = f"{self.base_url}/api/hosts/bulk/delete"
        try:
            r = requests.post(url, json={"ids": host_ids}, headers=self.headers, timeout=PG_TIMEOUT)
            return r.status_code in (200, 201)
        except Exception:
            return False

    @staticmethod
    def _host_matches_tags(group_tag, host: dict, tags: set, ports: set = None):
        if ports and host.get("port") in ports:
            return True
        for val in (
            group_tag,
            host.get("inbound_tag"),
            host.get("inboundTag"),
            host.get("tag"),
            host.get("remark"),
            host.get("name"),
        ):
            if val and val in tags:
                return True
        return False

    def delete_hosts_by_tags(self, tags: set, ports: set = None, quiet: bool = False):
        raw = self.get_hosts()
        if raw is None:
            return 0

        if isinstance(raw, dict) and "hosts" in raw:
            entries = [(h.get("inbound_tag") or h.get("tag") or "—", h) for h in raw["hosts"]]
        elif isinstance(raw, list):
            entries = [
                (h.get("inbound_tag") or h.get("tag") or h.get("inboundTag") or "—", h)
                for h in raw if isinstance(h, dict)
            ]
        else:
            entries = self._flatten_hosts(raw)

        ports = ports or set()
        ids_to_delete = []
        seen = set()
        for group_tag, h in entries:
            if not self._host_matches_tags(group_tag, h, tags, ports):
                continue
            hid = h.get("id")
            if hid is not None and hid not in seen:
                ids_to_delete.append(hid)
                seen.add(hid)

        if not ids_to_delete:
            if not quiet:
                print(f"{C_YELLOW}[!] No hosts matched for removal.{C_RESET}")
            return 0

        removed = 0
        if len(ids_to_delete) > 1 and self.bulk_delete_hosts(ids_to_delete):
            removed = len(ids_to_delete)
        else:
            for hid in ids_to_delete:
                if self.delete_host(hid, quiet=True):
                    removed += 1

        if not quiet:
            print(f"{C_CYAN}[~] Host(s) deleted: {removed}{C_RESET}")
        return removed

    def create_host(self, payload: dict):

        url = f"{self.base_url}/api/host"
        try:
            r = requests.post(url, json=payload, headers=self.headers, timeout=PG_TIMEOUT)
            if r.status_code in (200, 201):
                return True, None
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, str(e)

    def _flatten_hosts(self, data):
        flat = []
        if isinstance(data, dict):
            for group_tag, hosts in data.items():
                if isinstance(hosts, list):
                    for h in hosts:
                        flat.append((group_tag, h))
                elif isinstance(hosts, dict):
                    flat.append((group_tag, hosts))
        elif isinstance(data, list):
            for h in data:
                group_tag = h.get("inbound_tag") or h.get("tag") or h.get("inboundTag") or "—"
                flat.append((group_tag, h))
        return flat

    def append_host_clone(self, data, source_index: int, target_inbound_tag: str, new_remark: str):
        flat = self._flatten_hosts(data)
        if source_index < 1 or source_index > len(flat):
            return False
        _, source_host = flat[source_index - 1]
        new_host = copy.deepcopy(source_host)
        new_host.pop("id", None)
        new_host["remark"]      = new_remark
        new_host["inbound_tag"] = target_inbound_tag
        new_host["port"]        = None
        if "name" in new_host:
            new_host["name"] = new_remark
        if isinstance(data, list):
            data[:] = [h for h in data if not (
                h.get("inbound_tag") == target_inbound_tag and h.get("remark") == new_remark
            )]
            data.append(new_host)
        elif isinstance(data, dict):
            group = data.setdefault(target_inbound_tag, [])
            if not isinstance(group, list):
                group = [group]
                data[target_inbound_tag] = group
            data[target_inbound_tag] = [h for h in group if h.get("remark") != new_remark]
            data[target_inbound_tag].append(new_host)
        else:
            return False
        return True

    def remove_hosts_by_tags(self, data, tags: set):
        if isinstance(data, list):
            data[:] = [
                h for h in data
                if (h.get("inbound_tag") or h.get("tag") or h.get("inboundTag") or "") not in tags
            ]
            return True
        if isinstance(data, dict):
            for t in list(data.keys()):
                if t in tags:
                    del data[t]
            for group_tag in list(data.keys()):
                val = data[group_tag]
                if isinstance(val, list):
                    data[group_tag] = [
                        h for h in val
                        if (h.get("inbound_tag") or group_tag) not in tags
                    ]
                    if not data[group_tag]:
                        del data[group_tag]
                elif isinstance(val, dict):
                    ib_tag = val.get("inbound_tag") or group_tag
                    if ib_tag in tags or group_tag in tags:
                        del data[group_tag]
            return True
        return False

    def clone_host(self, source_index: int, target_inbound_tag: str, new_remark: str):
        raw = self.get_hosts()
        if raw is None:
            print(f"{C_RED}[-] Could not fetch hosts.{C_RESET}")
            return False
        data = copy.deepcopy(raw)
        if not self.append_host_clone(data, source_index, target_inbound_tag, new_remark):
            print(f"{C_RED}[-] Invalid host index.{C_RESET}")
            return False
        print(f"{C_GREEN}[+] Cloned host -> '{target_inbound_tag}' remark='{new_remark}'.{C_RESET}")
        return self.save_hosts(data)

def parse_expiry_datetime(expiry_date):

    if not expiry_date:
        return None
    raw = str(expiry_date).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        exp = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=_TZ_TEHRAN)
    return exp.astimezone(timezone.utc)

def format_license_remaining(expiry_date):

    if not expiry_date:
        return "∞", "\033[97m"
    exp = parse_expiry_datetime(expiry_date)
    if exp is None:
        return "N/A", "\033[91m"
    total_sec = (exp - datetime.now(timezone.utc)).total_seconds()
    if total_sec <= 0:
        return "Expired", "\033[91m"
    days = int(total_sec // 86400)
    if days > 0:
        color = "\033[93m" if days < 15 else "\033[97m"
        return f"{days} Days", color
    hours = int(total_sec // 3600)
    if hours > 0:
        return f"{hours} Hours", "\033[93m"
    mins = max(1, int(total_sec // 60))
    return f"{mins} Minutes", "\033[91m"

def detect_installed_panels():
    installed = []

    if os.path.exists(DB_PATH) or os.path.exists('/usr/local/x-ui/x-ui'):
        installed.append(("3X-UI", C_GREEN + "🟢 Installed" + C_RESET))
    else:
        installed.append(("3X-UI", C_WHITE + "⚪ Not Found" + C_RESET))

    pg_paths = ["/opt/pasarguard", "/opt/PasarGuard", "/etc/pasarguard", "/etc/PasarGuard"]
    if any(os.path.exists(p) for p in pg_paths):
        installed.append(("Pasargad", C_GREEN + "🟢 Installed" + C_RESET))
    else:
        installed.append(("Pasargad", C_WHITE + "⚪ Not Found" + C_RESET))

    marzban_paths = ["/opt/marzban", "/etc/marzban", "/usr/local/bin/marzban"]
    if any(os.path.exists(p) for p in marzban_paths):
        installed.append(("Marzban", C_GREEN + "🟢 Installed" + C_RESET))
    else:
        installed.append(("Marzban", C_WHITE + "⚪ Not Found" + C_RESET))
    return installed

def confirm_proceed(prompt="Are you sure you want to proceed?"):
    ans = input(f"\n{C_BOLD}{C_YELLOW}❓ {prompt} ({C_GREEN}y{C_YELLOW}/{C_RED}n{C_YELLOW}){C_RESET}: ").strip().lower()
    return ans == "y"

def _x3ui_normalize_url(url):
    url = url.strip()
    if not url:
        return url
    if not re.match(r'^https?://', url, re.I):
        url = "http://" + url
    return url.rstrip('/')

def x3ui_load_cached_creds():
    if not os.path.isfile(X3UI_CREDS_FILE):
        return None
    try:
        env = _parse_env_file(X3UI_CREDS_FILE)
        url, user, pw = env.get("URL", ""), env.get("USER", ""), env.get("PASS", "")
        if url and user and pw:
            return url, user, pw
    except Exception:
        pass
    return None

def x3ui_save_creds(url, user, pw):
    try:
        import stat
        with open(X3UI_CREDS_FILE, "w") as f:
            f.write(f"URL={url}\nUSER={user}\nPASS={pw}\n")
        try:
            os.chmod(X3UI_CREDS_FILE, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
        print(f"{C_GREEN}[+] Credentials saved.{C_RESET}")
    except Exception as e:
        print(f"{C_YELLOW}[!] Could not save credentials: {e}{C_RESET}")

def x3ui_resolve_credentials():
    cached = x3ui_load_cached_creds()
    if cached:
        url, user, pw = cached
        print(f"{C_GREEN}[+] Using saved credentials  URL={url}  user={user}{C_RESET}")
        return url, user, pw
    print(f"{C_YELLOW}[~] Enter your 3X-UI panel login details (include the web base path if any).{C_RESET}")
    url  = _x3ui_normalize_url(input("  Panel URL (e.g. https://panel.example.com:2053/xyz): ").strip())
    user = input("  Admin username: ").strip()
    pw   = input("  Admin password: ").strip()
    x3ui_save_creds(url, user, pw)
    return url, user, pw

def _x3ui_run_cli(args, timeout=25):
    if not os.path.exists(X3UI_BINARY):
        return None
    try:
        proc = subprocess.run(
            [X3UI_BINARY] + args,
            capture_output=True, text=True, timeout=timeout,
            cwd=os.path.dirname(X3UI_BINARY)
        )
        return f"{proc.stdout or ''}\n{proc.stderr or ''}"
    except Exception:
        return None

def _x3ui_build_base_url(scheme, port, base_path):
    base_path = (base_path or "").strip().strip('/')
    if base_path:
        return f"{scheme}://127.0.0.1:{port}/{base_path}"
    return f"{scheme}://127.0.0.1:{port}"

def _x3ui_load_token_cache():
    try:
        with open(X3UI_TOKEN_CACHE) as f:
            d = json.load(f)
        if d.get("url") and d.get("token"):
            return d["url"], d["token"]
    except Exception:
        pass
    return None

def _x3ui_save_token_cache(url, token):
    try:
        import stat
        with open(X3UI_TOKEN_CACHE, "w") as f:
            json.dump({"url": url, "token": token}, f)
        try:
            os.chmod(X3UI_TOKEN_CACHE, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
    except Exception:
        pass

def x3ui_auto_client():
    if not os.path.exists(X3UI_BINARY):
        return None

    cached = _x3ui_load_token_cache()
    if cached:
        url, token = cached
        try:
            c = ThreeXUIClient(base_url=url, api_token=token)
            ok, _ = c.test_connection()
            if ok:
                return c
        except Exception:
            pass

    show_out = _x3ui_run_cli(["setting", "-show"])
    if not show_out:
        return None
    m_port = re.search(r'(?mi)^\s*port:\s*(\d+)', show_out)
    if not m_port:
        return None
    port = m_port.group(1)
    m_bp = re.search(r'(?mi)^\s*webBasePath:\s*(\S*)', show_out)
    base_path = m_bp.group(1) if m_bp else ""

    cert_out = _x3ui_run_cli(["setting", "-getCert"]) or ""
    has_cert = bool(re.search(r'(?mi)^\s*cert:\s*\S+', cert_out))
    schemes = ["https", "http"] if has_cert else ["http", "https"]

    tok_out = _x3ui_run_cli(["setting", "-getApiToken"])
    if not tok_out:
        return None
    m_tok = re.search(r'(?mi)^\s*apiToken:\s*(\S+)', tok_out)
    if not m_tok:
        return None
    token = m_tok.group(1)

    for scheme in schemes:
        url = _x3ui_build_base_url(scheme, port, base_path)
        try:
            c = ThreeXUIClient(base_url=url, api_token=token)
            ok, _ = c.test_connection()
            if ok:
                _x3ui_save_token_cache(url, token)
                return c
        except Exception:
            continue
    return None

def parse_json_field(val):
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val

def _detect_url_from_pg_env():
    for path in ["/opt/pasarguard/.env", "/opt/PasarGuard/.env",
                 "/etc/pasarguard/.env", "/etc/PasarGuard/.env"]:
        if not os.path.isfile(path):
            continue
        try:
            env      = _parse_env_file(path)
            host     = env.get("UVICORN_HOST", "127.0.0.1").strip()
            port     = env.get("UVICORN_PORT", "8000").strip()
            certfile = env.get("UVICORN_SSL_CERTFILE", "").strip()
            connect_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
            scheme       = "https" if certfile else "http"
            domain = ""
            if certfile:
                for part in certfile.replace("\\", "/").split("/"):
                    if "." in part and not part.endswith(".pem"):
                        domain = part
                        break
            url = f"{scheme}://{domain}:{port}" if domain else f"{scheme}://{connect_host}:{port}"
            return url
        except Exception as e:
            print(f"{C_YELLOW}[!] Could not parse {path}: {e}{C_RESET}")
    return ""

def pg_load_cached_creds():
    if not os.path.isfile(PG_CREDS_FILE):
        return None
    try:
        env = _parse_env_file(PG_CREDS_FILE)
        url, user, pw = env.get("URL",""), env.get("USER",""), env.get("PASS","")
        if url and user and pw:
            return url, user, pw
    except Exception:
        pass
    return None

def pg_save_creds(url, user, pw):
    try:
        import stat
        with open(PG_CREDS_FILE, "w") as f:
            f.write(f"URL={url}\nUSER={user}\nPASS={pw}\n")
        os.chmod(PG_CREDS_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except Exception as e:
        print(f"{C_YELLOW}[!] Could not save credentials: {e}{C_RESET}")

def pg_resolve_credentials():
    from urllib.parse import urlparse
    cached = pg_load_cached_creds()
    if cached:
        url, user, pw = cached
        return url, user, pw
        
    detected_url = _detect_url_from_pg_env()
    url = None
    if detected_url:
        print(f"  \033[96m► Auto-detected URL: {detected_url}\033[0m")
        ans = input(f"  \033[93m❓ Use this panel address? (y/n):\033[0m ").strip().lower()
        if ans == 'y':
            url = detected_url
    if not url:
        scheme, domain, port, path = "https", "", "", "dashboard"
        if detected_url:
            parsed = urlparse(detected_url)
            scheme = parsed.scheme or "https"
            domain = parsed.hostname or ""
            port   = str(parsed.port) if parsed.port else ""
        while True:
            domain_in = input(f"  Panel domain (e.g. panel.example.com) [{domain}]: ").strip() or domain
            if "://" in domain_in or "/" in domain_in:
                raw = domain_in if "://" in domain_in else f"{scheme}://{domain_in}"
                parsed = urlparse(raw)
                if parsed.scheme:
                    scheme = parsed.scheme
                domain_in = parsed.hostname or domain_in.split("/")[0].split(":")[0]
                if parsed.port and not port:
                    port = str(parsed.port)
            port_in = input(f"  Panel port (e.g. 8443) [{port}]: ").strip() or port
            path_in = input(f"  Panel path (e.g. dashboard) [{path}]: ").strip() or path
            path_in = path_in.strip("/") or "dashboard"
            if not domain_in or not port_in:
                print(f"{C_RED}[-] Domain and port are required.{C_RESET}")
                continue
            dashboard_link = f"{scheme}://{domain_in}:{port_in}/{path_in}"
            print(f"  Dashboard link: {C_CYAN}{dashboard_link}{C_RESET}")
            if confirm_proceed(f"Is this the final dashboard link? ({dashboard_link})"):
                url = f"{scheme}://{domain_in}:{port_in}"
                break
            domain, port, path = domain_in, port_in, path_in
    user = input("  Admin username: ").strip()
    pw   = input("  Admin password: ").strip()
    pg_save_creds(url, user, pw)
    return url, user, pw

def _parse_env_file(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def _display_width(text):

    width = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        o = ord(ch)
        if unicodedata.combining(ch):
            i += 1
            continue
        if 0x1F1E6 <= o <= 0x1F1FF:
            width += 2
            i += 1
            if i < n and 0x1F1E6 <= ord(text[i]) <= 0x1F1FF:
                i += 1
            while i < n and ord(text[i]) in (0xFE0F, 0x200D):
                i += 1
            continue
        if o >= 0x1F000 or unicodedata.east_asian_width(ch) in ("F", "W"):
            width += 2
        else:
            width += 1
        i += 1
    return width

def _pad_display(text, width):
    return text + (" " * max(0, width - _display_width(text)))

def _ascii_pad(text, width):

    text = str(text or "")
    if len(text) > width:
        text = text[: width - 1] + "…"
    return text + (" " * max(0, width - len(text)))

def _normalize_country_name(name):
    name_clean = str(name or "").lower().strip()
    name_clean = re.sub(r"^[\U0001F1E0-\U0001F1FF\U0001F300-\U0001FAFF]+\s*", "", name_clean)
    name_clean = name_clean.replace("the ", "").strip()
    name_clean = re.sub(r"\s+", " ", name_clean)
    name_clean = re.sub(r"\s+(dc|datacenter)\s*$", "", name_clean).strip()
    name_ascii = "".join(
        c for c in unicodedata.normalize("NFD", name_clean)
        if unicodedata.category(c) != "Mn"
    )
    return name_clean, name_ascii

_COUNTRY_META = {
    "germany": ("🇩🇪", "DE"), "turkey": ("🇹🇷", "TR"), "turkiye": ("🇹🇷", "TR"),
    "united states": ("🇺🇸", "US"), "usa": ("🇺🇸", "US"), "us": ("🇺🇸", "US"),
    "france": ("🇫🇷", "FR"), "austria": ("🇦🇹", "AT"), "canada": ("🇨🇦", "CA"),
    "finland": ("🇫🇮", "FI"), "poland": ("🇵🇱", "PL"), "luxembourg": ("🇱🇺", "LU"),
    "israel": ("🇮🇱", "IL"), "united kingdom": ("🇬🇧", "GB"), "uk": ("🇬🇧", "GB"),
    "netherlands": ("🇳🇱", "NL"), "russia": ("🇷🇺", "RU"), "switzerland": ("🇨🇭", "CH"),
    "japan": ("🇯🇵", "JP"), "singapore": ("🇸🇬", "SG"), "australia": ("🇦🇺", "AU"),
    "spain": ("🇪🇸", "ES"), "italy": ("🇮🇹", "IT"), "sweden": ("🇸🇪", "SE"),
    "norway": ("🇳🇴", "NO"), "brazil": ("🇧🇷", "BR"), "argentina": ("🇦🇷", "AR"),
    "chile": ("🇨🇱", "CL"), "mexico": ("🇲🇽", "MX"), "south korea": ("🇰🇷", "KR"),
    "india": ("🇮🇳", "IN"), "indonesia": ("🇮🇩", "ID"), "malaysia": ("🇲🇾", "MY"),
    "thailand": ("🇹🇭", "TH"), "vietnam": ("🇻🇳", "VN"), "philippines": ("🇵🇭", "PH"),
    "taiwan": ("🇹🇼", "TW"), "hong kong": ("🇭🇰", "HK"), "south africa": ("🇿🇦", "ZA"),
    "egypt": ("🇪🇬", "EG"), "nigeria": ("🇳🇬", "NG"), "kenya": ("🇰🇪", "KE"),
    "saudi arabia": ("🇸🇦", "SA"), "uae": ("🇦🇪", "AE"), "united arab emirates": ("🇦🇪", "AE"),
    "ireland": ("🇮🇪", "IE"), "belgium": ("🇧🇪", "BE"), "denmark": ("🇩🇰", "DK"),
    "portugal": ("🇵🇹", "PT"), "greece": ("🇬🇷", "GR"), "czech republic": ("🇨🇿", "CZ"),
    "czechia": ("🇨🇿", "CZ"), "romania": ("🇷🇴", "RO"), "hungary": ("🇭🇺", "HU"),
    "bulgaria": ("🇧🇬", "BG"), "ukraine": ("🇺🇦", "UA"), "new zealand": ("🇳🇿", "NZ"),
    "lithuania": ("🇱🇹", "LT"), "latvia": ("🇱🇻", "LV"), "estonia": ("🇪🇪", "EE"),
    "slovakia": ("🇸🇰", "SK"), "slovenia": ("🇸🇮", "SI"), "croatia": ("🇭🇷", "HR"),
    "serbia": ("🇷🇸", "RS"), "georgia": ("🇬🇪", "GE"), "armenia": ("🇦🇲", "AM"),
    "azerbaijan": ("🇦🇿", "AZ"), "kazakhstan": ("🇰🇿", "KZ"), "cyprus": ("🇨🇾", "CY"),
    "iceland": ("🇮🇸", "IS"), "malta": ("🇲🇹", "MT"), "moldova": ("🇲🇩", "MD"),
    "belarus": ("🇧🇾", "BY"),
}

def _lookup_country_meta(name):
    name_clean, name_ascii = _normalize_country_name(name)
    if name_clean in _COUNTRY_META:
        return _COUNTRY_META[name_clean]
    if name_ascii in _COUNTRY_META:
        return _COUNTRY_META[name_ascii]
    for key, meta in sorted(_COUNTRY_META.items(), key=lambda kv: -len(kv[0])):
        if name_clean.startswith(key + " ") or name_ascii.startswith(key + " "):
            return meta
    return ("🌐", "XX")

def get_country_flag(name):
    return _lookup_country_meta(name)[0]

def get_country_iso(name):
    return _lookup_country_meta(name)[1]

def pg_show_inbounds(inbounds, title="Select Inbound to Clone From"):
    b = "\033[96m"
    t = "\033[97m"
    x = "\033[0m"
    pad = max(0, 74 - len(title))
    l1 = pad // 2
    r1 = pad - l1
    print(f"\n  {b}╭──────────────────────────────────────────────────────────────────────────╮{x}")
    print(f"  {b}│{x}{' ' * l1}{t}{title}{x}{' ' * r1}{b}│{x}")
    print(f"  {b}├──────┬─────────────────────────┬────────┬──────────┬──────────┬──────────┤{x}")
    print(f"  {b}│{x} \033[1mOpt.\033[0m {b}│{x} \033[1mTag\033[0m                     {b}│{x} \033[1mPort\033[0m   {b}│{x} \033[1mProtocol\033[0m {b}│{x} \033[1mNetwork\033[0m  {b}│{x} \033[1mSecurity\033[0m {b}│{x}")
    print(f"  {b}├──────┼─────────────────────────┼────────┼──────────┼──────────┼──────────┤{x}")
    for i, ib in enumerate(inbounds, 1):
        tag      = ib.get("remark") or ib.get("tag") or "—"
        tag_fmt  = tag[:23].ljust(23)
        protocol = ib.get("protocol", "?")[:8].ljust(8)
        port     = str(ib.get("port", "?"))[:6].ljust(6)
        ss       = ib.get("streamSettings", {}) or {}
        network  = ss.get("network", "tcp")[:8].ljust(8)
        security = ss.get("security", "none")[:8].ljust(8)
        print(f"  {b}│{x} \033[93m[{i:02d}]\033[0m {b}│{x} {t}{tag_fmt}{x} {b}│{x} {C_WHITE}{port}{x} {b}│{x} {C_CYAN}{protocol}{x} {b}│{x} {C_MAGENTA}{network}{x} {b}│{x} {C_GREEN}{security}{x} {b}│{x}")
    print(f"  {b}├──────┴─────────────────────────┴────────┴──────────┴──────────┴──────────┤{x}")
    print(f"  {b}│{x} \033[97m0. Back\033[0m                                                                  {b}│{x}")
    print(f"  {b}╰──────────────────────────────────────────────────────────────────────────╯{x}\n")

def _pg_country_tag(country: dict):
    flag = country.get('flag') or get_country_flag(country.get('name', ''))
    return f"{flag} {country['name']}"

def _pg_apply_inbound_outbound(config: dict, source_inbound: dict, country: dict):
    inbound_tag = _pg_country_tag(country)
    inbounds    = config.setdefault("inbounds", [])
    outbounds   = config.setdefault("outbounds", [])

    inbounds[:]  = [ib for ib in inbounds
                    if ib.get("port") != country['in_port'] and ib.get("tag") != inbound_tag]
    outbounds[:] = [ob for ob in outbounds 
                    if ob.get("tag") != inbound_tag
                    and not (ob.get("protocol") == "socks" 
                             and ob.get("settings", {}).get("address") == "10.0.0.1" 
                             and str(ob.get("settings", {}).get("port")) == str(country['out_port']))]

    new_inbound         = copy.deepcopy(source_inbound)
    new_inbound["port"] = country['in_port']
    new_inbound["tag"]  = inbound_tag
    inbounds.append(new_inbound)

    outbounds.append({
        "tag":      inbound_tag,
        "protocol": "socks",
        "settings": {"address": "10.0.0.1", "port": int(country['out_port'])}
    })
    return inbound_tag

def x3ui_clone_countries_batch(api: ThreeXUIClient, source_inbound: dict, countries: list):
    if not countries:
        return 0

    import os
    os.system("cls" if os.name == "nt" else "clear")

    b = "\033[96m"
    t = "\033[97m"
    x = "\033[0m"
    print(f"\n  {b}╭──────────────────────────────────────────────────╮{x}")
    print(f"  {b}│{x}                 {t}Install Location{x}                 {b}│{x}")
    print(f"  {b}╰──────────────────────────────────────────────────╯{x}\n")

    print(f"  {C_CYAN}❖{C_RESET} {C_BOLD}Fetching 3X-UI Xray settings...{C_RESET}")
    success, settings = api.get_xray_setting()
    if not success or not settings:
        print(f"  {C_RED}✖ Failed to fetch Xray settings.{C_RESET}")
        return 0

    if isinstance(settings, str):
        settings = json.loads(settings)
    xray_setting = settings.get("xraySetting", "{}")
    xray_config  = json.loads(xray_setting) if isinstance(xray_setting, str) else xray_setting
    outbounds = xray_config.setdefault("outbounds", [])
    routing = xray_config.setdefault("routing", {})
    rules = routing.setdefault("rules", [])

    print(f"  {C_BLUE}[1/4]{C_RESET} 📦 Creating panel inbounds...")
    created = 0
    for country in countries:
        flag = country.get('flag', '🌐')
        inbound_tag = f"{flag} {country['name']}"
        outbound_tag = f"Datacenter-{country['name']}"

        outbounds[:] = [ob for ob in outbounds if ob.get("tag") != outbound_tag]
        rules[:] = [r for r in rules if inbound_tag not in r.get("inboundTag", []) and r.get("outboundTag") != outbound_tag]

        inbound_payload = {
            "enable": True,
            "remark": inbound_tag,
            "listen": source_inbound.get("listen", ""),
            "port": country['in_port'],
            "protocol": source_inbound.get("protocol"),
            "expiryTime": 0,
            "total": 0,
            "tag": inbound_tag,
            "settings": parse_json_field(source_inbound.get("settings")),
            "streamSettings": parse_json_field(source_inbound.get("streamSettings")),
            "sniffing": parse_json_field(source_inbound.get("sniffing"))
        }
        
        inbound_ok, _ = api.create_inbound(inbound_payload)
        if not inbound_ok:
            print(f"        {C_RED}✖ Failed inbound: {inbound_tag}{C_RESET}")
            continue

        outbounds.append({
            "protocol": "socks",
            "settings": {"servers": [{"address": "10.0.0.1", "port": int(country['out_port'])}]},
            "tag": outbound_tag
        })

        rules.append({
            "type": "field",
            "inboundTag": [inbound_tag],
            "outboundTag": outbound_tag
        })

        created += 1

    if created > 0:
        print(f"  {C_BLUE}[2/4]{C_RESET} 🔀 Saving routing & outbounds...")
        outbound_test_url = settings.get("outboundTestUrl", "https://www.google.com/generate_204")
        if api.update_xray_setting(json.dumps(xray_config, indent=2), outbound_test_url):
            print(f"  {C_BLUE}[3/4]{C_RESET} 🔄 Restarting Xray service...")
            if api.restart_xray_service():
                print(f"  {C_GREEN}✔ Xray restarted successfully.{C_RESET}")
            else:
                print(f"  {C_YELLOW}⚠ Failed to restart Xray.{C_RESET}")
                
            print(f"  {C_BLUE}[4/4]{C_RESET} 🌐 Verifying deployment...\n")
            for country in countries:
                flag = country.get('flag', '🌐')
                print(f"  {C_GREEN}✅ {flag} {country['name']} | In: {country['in_port']} ➔ Out: {country['out_port']}{C_RESET}")

    return created

def pg_clone_countries_batch(api: PasarGuardAPI, source_inbound: dict,
                             countries: list, host_index: int):

    if not countries:
        return 0
        
    import os
    os.system("cls" if os.name == "nt" else "clear")
        
    b = "\033[96m"
    t = "\033[97m"
    x = "\033[0m"
    print(f"\n  {b}╭──────────────────────────────────────────────────╮{x}")
    print(f"  {b}│{x}                 {t}Install Location{x}                 {b}│{x}")
    print(f"  {b}╰──────────────────────────────────────────────────╯{x}\n")

    print(f"  {C_CYAN}❖{C_RESET} {C_BOLD}Fetching core config...{C_RESET}")
    config = api.get_core_config()
    if config is None:
        print(f"  {C_RED}✖ Could not fetch core config.{C_RESET}")
        return 0

    prepared = []
    for country in countries:
        tag = _pg_apply_inbound_outbound(config, source_inbound, country)
        prepared.append((country, tag))

    print(f"  {C_BLUE}[1/5]{C_RESET} 📦 Saving inbound & outbound...")
    if not api.save_core_config(config, restart_nodes=False):
        print(f"  {C_RED}✖ Failed to save inbound/outbound.{C_RESET}")
        return 0

    for _, tag in prepared:
        _pg_apply_routing(config, tag)

    print(f"  {C_BLUE}[2/5]{C_RESET} 🔀 Saving routing rules...")
    if not api.save_core_config(config, restart_nodes=False):
        print(f"  {C_RED}✖ Failed to save routing.{C_RESET}")
        return 0

    print(f"  {C_BLUE}[3/5]{C_RESET} 🔄 Restarting Xray service...")
    if api.restart_core(quiet=True):
        print(f"  {C_GREEN}✔ Xray restarted successfully.{C_RESET}")
    else:
        print(f"  {C_YELLOW}⚠ Failed to restart Xray.{C_RESET}")

    print(f"  {C_BLUE}[4/5]{C_RESET} ⏳ Waiting {PG_HOST_WAIT}s for Xray to stabilize...")
    time.sleep(PG_HOST_WAIT)

    print(f"  {C_BLUE}[5/5]{C_RESET} 🌐 Adding hosts to panel...\n")
    config = api.get_core_config()
    raw_hosts = api.get_hosts()
    if raw_hosts is None:
        for country, tag in prepared:
            print(f"  {C_YELLOW}⚠  {tag}{C_RESET} — core OK, hosts fetch failed.")
        return 0

    flat = api._flatten_hosts(raw_hosts)
    if host_index < 1 or host_index > len(flat):
        print(f"  {C_RED}✖ Invalid source host index.{C_RESET}")
        return 0
    _, source_host = flat[host_index - 1]

    success = 0
    for country, expected_tag in prepared:
        actual_tag = _pg_resolve_inbound_tag(config, country) or expected_tag
        payload    = _pg_sanitize_host_payload(source_host, actual_tag, actual_tag)

        ok, err = False, None
        for attempt in range(3):
            ok, err = api.create_host(payload)
            if ok:
                break
            if err and "not found" in err.lower() and attempt < 2:
                print(f"  {C_YELLOW}⚠ Inbound not ready, retrying in 5s...{C_RESET}")
                time.sleep(5)
                config = api.get_core_config() or config
                actual_tag = _pg_resolve_inbound_tag(config, country) or actual_tag
                payload["inbound_tag"] = actual_tag
                payload["remark"]      = actual_tag
                continue
            break

        if ok:
            print(f"  {C_GREEN}✅ {actual_tag}{C_RESET} | In: {C_CYAN}{country['in_port']}{C_RESET}"
                  f" ➔ Out: {C_YELLOW}{country['out_port']}{C_RESET}")
            success += 1
        else:
            print(f"  {C_RED}❌ {actual_tag}{C_RESET} — host failed: {err or 'unknown error'}")

    return success

def pg_delete_countries_batch(api: PasarGuardAPI, countries: list):

    if not countries:
        return 0

    import os
    os.system("cls" if os.name == "nt" else "clear")

    b = "\033[96m"
    t = "\033[97m"
    x = "\033[0m"
    print(f"\n  {b}╭──────────────────────────────────────────────────╮{x}")
    print(f"  {b}│{x}                {t}Datacenter Removal{x}                {b}│{x}")
    print(f"  {b}╰──────────────────────────────────────────────────╯{x}\n")

    match_tags = _pg_match_tags_for_countries(countries)
    match_ports = {c['in_port'] for c in countries if c.get('in_port') is not None}

    print(f"  {C_BLUE}[1/2]{C_RESET} 🗑️  Removing panel hosts...")
    removed_h = api.delete_hosts_by_tags(match_tags, ports=match_ports, quiet=True)
    if removed_h:
        print(f"  {C_GREEN}✔ {removed_h} Hosts removed.{C_RESET}")
    else:
        print(f"  {C_YELLOW}⚠ No matching hosts found.{C_RESET}")

    print(f"  {C_BLUE}[2/2]{C_RESET} 🧹 Cleaning core config (inbounds & routing)...")
    config = api.get_core_config()
    if config is None:
        print(f"  {C_RED}✖ Could not fetch core config.{C_RESET}")
        return 0

    all_removed_tags = set()
    for country in countries:
        all_removed_tags |= _pg_remove_country_from_config(config, country)

    if all_removed_tags:
        api.delete_hosts_by_tags(all_removed_tags, ports=match_ports, quiet=True)

    if not api.save_core_config(config, restart_nodes=False):
        print(f"  {C_RED}✖ Failed to save core config.{C_RESET}")
        return 0

    print(f"  {C_CYAN}❖{C_RESET} {C_BOLD}Restarting Xray service...{C_RESET}")
    if not api.restart_core(quiet=True):
        print(f"  {C_YELLOW}⚠ Config saved but xray restart failed — check panel.{C_RESET}")
    else:
        print(f"  {C_GREEN}✔ Xray restarted successfully.{C_RESET}")

    print()
    for country in countries:
        print(f"  {C_GREEN}✅ Removed:{C_RESET} {_pg_country_tag(country)}")
    return len(countries)

def pg_clone_inbound_for_country(api: PasarGuardAPI, source_inbound: dict,
                                  country: dict, host_index: int,
                                  restart_nodes: bool = True):

    return pg_clone_countries_batch(api, source_inbound, [country], host_index) >= 1

def x3ui_execute_deletion(api: ThreeXUIClient, selected_countries: list):
    if not selected_countries:
        return 0

    import os
    os.system("cls" if os.name == "nt" else "clear")

    b = "\033[96m"
    t = "\033[97m"
    x = "\033[0m"
    print(f"\n  {b}╭──────────────────────────────────────────────────╮{x}")
    print(f"  {b}│{x}                {t}Datacenter Removal{x}                {b}│{x}")
    print(f"  {b}╰──────────────────────────────────────────────────╯{x}\n")

    print(f"  {C_BLUE}[1/2]{C_RESET} 🗑️  Removing panel inbounds...")
    success, inbounds = api.get_inbounds()
    if not success:
        print(f"  {C_RED}✖ Failed to fetch inbounds for deletion.{C_RESET}")
        return 0
        
    success, settings = api.get_xray_setting()
    if not success or not settings:
        print(f"  {C_RED}✖ Failed to fetch Xray settings.{C_RESET}")
        return 0

    if isinstance(settings, str):
        settings = json.loads(settings)
    xray_setting = settings.get("xraySetting", "{}")
    xray_config  = json.loads(xray_setting) if isinstance(xray_setting, str) else xray_setting
    outbounds = xray_config.setdefault("outbounds", [])
    routing = xray_config.setdefault("routing", {})
    rules = routing.setdefault("rules", [])

    removed = 0
    for country in selected_countries:
        in_port = country.get('in_port')
        flag = country.get('flag', '🌐')
        inbound_tag = f"{flag} {country['name']}"
        outbound_tag = f"Datacenter-{country['name']}"

        for ib in inbounds:
            if ib.get("port") == in_port or ib.get("remark") == inbound_tag:
                api.delete_inbound(ib.get("id"))

        outbounds[:] = [ob for ob in outbounds if ob.get("tag") != outbound_tag]
        rules[:] = [r for r in rules if inbound_tag not in r.get("inboundTag", []) and r.get("outboundTag") != outbound_tag]
        
        removed += 1
        print(f"  {C_GREEN}✔ Removed:{C_RESET} {inbound_tag}")

    if removed > 0:
        print(f"  {C_BLUE}[2/2]{C_RESET} 🧹 Cleaning core config (inbounds & routing)...")
        outbound_test_url = settings.get("outboundTestUrl", "https://www.google.com/generate_204")
        if api.update_xray_setting(json.dumps(xray_config, indent=2), outbound_test_url):
            print(f"  {C_CYAN}❖{C_RESET} {C_BOLD}Restarting Xray service...{C_RESET}")
            if api.restart_xray_service():
                print(f"  {C_GREEN}✔ Xray restarted successfully.{C_RESET}")
            else:
                print(f"  {C_YELLOW}⚠ Failed to restart Xray.{C_RESET}")
            
    return removed

def pg_execute_deletion(api: PasarGuardAPI, selected_countries: list):

    return pg_delete_countries_batch(api, selected_countries)

def pg_show_hosts(api: PasarGuardAPI, title="Select Host to Clone From"):
    raw  = api.get_hosts()
    if raw is None:
        return None, []
    flat = api._flatten_hosts(raw)
    if not flat:
        print(f"{C_YELLOW}[i] No hosts found.{C_RESET}")
        return raw, []
        
    b = "\033[96m"
    t = "\033[97m"
    x = "\033[0m"
    pad = max(0, 75 - len(title))
    l1 = pad // 2
    r1 = pad - l1
    print(f"\n  {b}╭───────────────────────────────────────────────────────────────────────────╮{x}")
    print(f"  {b}│{x}{' ' * l1}{t}{title}{x}{' ' * r1}{b}│{x}")
    print(f"  {b}├──────┬────────────────────┬──────────────────┬────────┬───────────────────┤{x}")
    print(f"  {b}│{x} \033[1mOpt.\033[0m {b}│{x} \033[1mRemark\033[0m             {b}│{x} \033[1mInbound Tag\033[0m      {b}│{x} \033[1mPort\033[0m   {b}│{x} \033[1mAddress\033[0m           {b}│{x}")
    print(f"  {b}├──────┼────────────────────┼──────────────────┼────────┼───────────────────┤{x}")
    import re
    for i, (group_tag, h) in enumerate(flat, 1):
        remark  = str(h.get("remark") or h.get("name") or "—")
        remark  = re.sub(r'[^\u0020-\u007E\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', '', remark)
        remark_fmt = remark[:17].ljust(18)
        address = str(h.get("address", "—"))
        if address.startswith("['") and address.endswith("']"):
            address = address[2:-2]
        elif address.startswith('["') and address.endswith('"]'):
            address = address[2:-2]
        address_fmt = address[:17].ljust(17)
        port    = str(h.get("port", "?"))
        if port == "None": port = "—"
        port_fmt = port[:6].ljust(6)
        tag_str = str(group_tag)
        tag_fmt = tag_str[:16].ljust(16)
        print(f"  {b}│{x} \033[93m[{i:02d}]\033[0m {b}│{x} {t}{remark_fmt}{x} {b}│{x} {C_CYAN}{tag_fmt}{x} {b}│{x} {C_WHITE}{port_fmt}{x} {b}│{x} {C_GREEN}{address_fmt}{x} {b}│{x}")
    print(f"  {b}├──────┴────────────────────┴──────────────────┴────────┴───────────────────┤{x}")
    print(f"  {b}│{x} \033[97m0. Back\033[0m                                                                   {b}│{x}")
    print(f"  {b}╰───────────────────────────────────────────────────────────────────────────╯{x}\n")
    return raw, flat

def x3ui_pick_inbound(api: ThreeXUIClient):
    success, inbounds = api.get_inbounds()
    if not success or not inbounds:
        print(f"{C_RED}[-] No inbounds available.{C_RESET}")
        return None
    pg_show_inbounds(inbounds, "Select Inbound to Clone From")
    print(f"\n{C_BOLD}Enter inbound # (or press Enter to go back):{C_RESET}")
    while True:
        val = input("> ").strip()
        if not val or val == "0":
            return None
        try:
            idx = int(val)
            if 1 <= idx <= len(inbounds):
                return inbounds[idx - 1]
            print(f"{C_RED}❌ Must be 1 – {len(inbounds)}.{C_RESET}")
        except ValueError:
            print(f"{C_RED}❌ Invalid number.{C_RESET}")

def pg_pick_inbound(api: PasarGuardAPI):
    inbounds = api.list_inbounds_raw()
    if not inbounds:
        print(f"{C_RED}[-] No inbounds available.{C_RESET}")
        return None
    pg_show_inbounds(inbounds, "Select Inbound to Clone From")
    print(f"\n{C_BOLD}Enter inbound # (or press Enter to go back):{C_RESET}")
    while True:
        val = input("> ").strip()
        if not val or val == "0":
            return None
        try:
            idx = int(val)
            if 1 <= idx <= len(inbounds):
                return inbounds[idx - 1]
            print(f"{C_RED}❌ Must be 1 – {len(inbounds)}.{C_RESET}")
        except ValueError:
            print(f"{C_RED}❌ Invalid number.{C_RESET}")

def pg_pick_host(api: PasarGuardAPI):
    _, flat = pg_show_hosts(api, "Select Host to Clone From")
    if not flat:
        return None
    print(f"\n{C_BOLD}Enter host # (or press Enter to go back):{C_RESET}")
    while True:
        val = input("> ").strip()
        if not val or val == "0":
            return None
        try:
            idx = int(val)
            if 1 <= idx <= len(flat):
                return idx
            print(f"{C_RED}❌ Must be 1 – {len(flat)}.{C_RESET}")
        except ValueError:
            print(f"{C_RED}❌ Invalid number.{C_RESET}")

def parse_selection(input_str, max_limit):
    selected = set()
    parts = input_str.replace(" ", "").split(",")
    for part in parts:
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                s, e = int(start), int(end)
                if 1 <= s <= max_limit and 1 <= e <= max_limit:
                    selected.update(range(min(s, e), max(s, e) + 1))
            except ValueError:
                continue
        else:
            try:
                v = int(part)
                if 1 <= v <= max_limit:
                    selected.add(v)
            except ValueError:
                continue
    return sorted(list(selected))

def _pg_apply_routing(config: dict, inbound_tag: str):
    routing = config.setdefault("routing", {})
    rules   = routing.setdefault("rules", [])
    rules[:] = [r for r in rules
                if not (inbound_tag in r.get("inboundTag", []) or r.get("outboundTag") == inbound_tag)]
    rules.append({"type": "field", "inboundTag": [inbound_tag], "outboundTag": inbound_tag})

def _pg_resolve_inbound_tag(config: dict, country: dict):
    port = country.get('in_port')
    expected = _pg_country_tag(country)
    if config:
        for ib in config.get("inbounds", []):
            if ib.get("port") == port:
                return ib.get("tag") or expected
            if ib.get("tag") == expected:
                return ib.get("tag")
    return expected

def _pg_match_tags_for_countries(countries: list):
    tags = set()
    for c in countries:
        tags.add(_pg_country_tag(c))
        tags.add(c['name'])
    return tags

def _pg_sanitize_host_payload(source_host: dict, inbound_tag: str, remark: str):
    p = copy.deepcopy(source_host)
    for k in ("id", "address_str"):
        p.pop(k, None)

    p["remark"]      = remark
    p["inbound_tag"] = inbound_tag
    p["port"]        = None

    addr = p.get("address")
    if isinstance(addr, set):
        p["address"] = sorted(str(a) for a in addr if a)
    elif isinstance(addr, list):
        p["address"] = [str(a) for a in addr if a]
    elif isinstance(addr, str) and addr.strip():
        p["address"] = [a.strip() for a in addr.split(",") if a.strip()]
    if not p.get("address"):
        p["address"] = ["127.0.0.1"]

    for field in ("sni", "host", "status", "verify_peer_cert_by_name"):
        v = p.get(field)
        if isinstance(v, set):
            p[field] = sorted(v)
        elif v is None:
            p[field] = []

    if p.get("priority") is None:
        p["priority"] = 0

    if "name" in p:
        p["name"] = remark
    return p

def _pg_remove_country_from_config(config: dict, country: dict):
    expected = _pg_country_tag(country)
    port     = country.get('in_port')
    use_port = isinstance(port, int) and port > 0
    tags_to_remove = {expected}

    for ib in config.get("inbounds", []):
        if ib.get("tag") == expected or (use_port and ib.get("port") == port):
            if ib.get("tag"):
                tags_to_remove.add(ib.get("tag"))

    config["inbounds"] = [
        ib for ib in config.get("inbounds", [])
        if ib.get("tag") not in tags_to_remove and not (use_port and ib.get("port") == port)
    ]
    for tag in tags_to_remove:
        config["outbounds"] = [ob for ob in config.get("outbounds", []) if ob.get("tag") != tag]

    routing = config.setdefault("routing", {})
    rules   = routing.setdefault("rules", [])
    routing["rules"] = [
        r for r in rules
        if not any(t in r.get("inboundTag", []) for t in tags_to_remove)
        and r.get("outboundTag") not in tags_to_remove
    ]
    return tags_to_remove

def clear_screen():
    os.system("clear")

def print_header(title):
    print("\033[96m" + "=" * 50 + "\033[0m")
    print(f"\033[1m {title}\033[0m")
    print("\033[96m" + "=" * 50 + "\033[0m\n")

def print_info(msg):
    print(f"\033[96m[i] {msg}\033[0m")

def print_success(msg):
    print(f"\033[92m[+] {msg}\033[0m")

def print_error(msg):
    print(f"\033[91m[-] {msg}\033[0m")

def print_warning(msg):
    print(f"\033[93m[!] {msg}\033[0m")


def select_panel():
    installed = detect_installed_panels()
    active_panels = [name for name, status in installed if "Installed" in status]
    
    if len(active_panels) == 1:
        return active_panels[0]
    elif len(active_panels) == 0:
        print(f"\n  \033[91m[-] No supported panel found on this server.\033[0m")
        print(f"  \033[96m[i] If Pasargad is installed on another server, you can connect remotely.\033[0m")
        if confirm_proceed("Continue with remote Pasargad setup?"):
            return "Pasargad"
        return None
        
    print(f"\n\033[96mMultiple Installed Panels Detected:\033[0m")
    idx = 1
    valid_choices = {}
    for name in active_panels:
        print(f"  {idx}. {name}")
        valid_choices[str(idx)] = name
        idx += 1
    print(f"  0. Cancel")
    
    choice = input(f"\n\033[96m> Select Panel to configure: \033[0m").strip()
    if choice == "0":
        return None
    return valid_choices.get(choice)

def install_datacenter_locations(panel_client, panel_name, datacenter_proxies):
    if not datacenter_proxies:
        print(f"{C_YELLOW}📦 No active Datacenter locations found. Connect your Datacenter first.{C_RESET}")
        input(f"\nPress {C_BOLD}{C_WHITE}[Enter]{C_RESET} to return...")
        return

    used_ports = set()
    active_inbound_tags = set()
    installed_dc_ports = set()
    
    if panel_name == "Pasargad":
        config = panel_client.get_core_config()
        if not config:
            print(f"{C_RED}❌ Failed to fetch core config.{C_RESET}")
            time.sleep(2)
            return
            
        used_ports = {ib.get("port") for ib in config.get("inbounds", []) if isinstance(ib.get("port"), int)}
        active_inbound_tags = {ib.get("tag") for ib in config.get("inbounds", []) if ib.get("tag")}
        
        for ob in config.get("outbounds", []):
            if ob.get("protocol") == "socks" and ob.get("settings", {}).get("address") == "10.0.0.1":
                if ob.get("tag") in active_inbound_tags:
                    installed_dc_ports.add(str(ob.get("settings", {}).get("port")))
                    
    elif panel_name == "3X-UI":
        success, inbounds = panel_client.get_inbounds()
        if not success:
            print(f"{C_RED}❌ Failed to fetch inbounds.{C_RESET}")
            time.sleep(2)
            return
            
        used_ports = {ib.get("port") for ib in inbounds if isinstance(ib.get("port"), int)}
        active_inbound_tags = {ib.get("remark") for ib in inbounds if ib.get("remark")}
        
        success, settings = panel_client.get_xray_setting()
        if success and settings:
            if isinstance(settings, str):
                settings = json.loads(settings)
            xray_setting = settings.get("xraySetting", "{}")
            xray_config  = json.loads(xray_setting) if isinstance(xray_setting, str) else xray_setting
            
            for ob in xray_config.get("outbounds", []):
                if ob.get("protocol") == "socks" and ob.get("settings", {}).get("servers"):
                    servers = ob.get("settings", {}).get("servers", [])
                    if servers and servers[0].get("address") == "10.0.0.1":
                        installed_dc_ports.add(str(servers[0].get("port")))

    unconfigured = []
    current_assign_port = 5050
    
    for port, data in datacenter_proxies.items():
        if str(port) in installed_dc_ports:
            continue
            
        while current_assign_port in used_ports:
            current_assign_port += 1
            
        c_name = data.get('country', 'Unknown')
        unconfigured.append({
            "name": c_name,
            "in_port": current_assign_port, 
            "out_port": int(port),
            "flag": get_country_flag(c_name)
        })
        used_ports.add(current_assign_port)
        
    if not unconfigured:
        print(f"{C_GREEN}🎉 All active Datacenter locations are already installed!{C_RESET}")
        input(f"\nPress {C_BOLD}{C_WHITE}[Enter]{C_RESET} to return...")
        return
        
    while True:
        clear_screen()
        b = "\033[96m"
        t = "\033[97m"
        x = "\033[0m"
        print(f"\n  {b}╭──────────────────────────────────────────────────╮{x}")
        print(f"  {b}│{x}{' ' * 16}{t}Install Locations{x}{' ' * 17}{b}│{x}")
        print(f"  {b}├──────┬────────────────────────────────┬──────────┤{x}")
        print(f"  {b}│{x} \033[1mOpt.\033[0m {b}│{x} \033[1mLocation\033[0m                       {b}│{x} \033[1mPort\033[0m     {b}│{x}")
        print(f"  {b}├──────┼────────────────────────────────┼──────────┤{x}")
        for i, node in enumerate(unconfigured, 1):
            cname = node.get('name', 'Unknown')
            iso = get_country_iso(cname)
 
            loc_col = _ascii_pad(f"[{iso}] {cname}", 30)
            port_col = f"{node['out_port']:<8}"
            print(f"  {b}│{x} \033[93m[{i:02d}]\033[0m {b}│{x} {t}{loc_col}{x} {b}│{x} \033[96m{port_col}\033[0m {b}│{x}")
        print(f"  {b}├──────┴────────────────────────────────┴──────────┤{x}")
        print(f"  {b}│{x} \033[97m0. Back\033[0m                                          {b}│{x}")
        print(f"  {b}╰──────────────────────────────────────────────────╯{x}\n")
        
        node_input = input(f"  \033[96m>\033[0m Select node(s) (e.g. 1 or 1-3,5): ").strip()
        if node_input in ("0", ""):
            return
            
        selected_indices = parse_selection(node_input, len(unconfigured))
        if not selected_indices:
            print(f"{C_RED}❌ Invalid selection.{C_RESET}")
            time.sleep(1.5)
            continue
            
        selected_nodes = [unconfigured[i - 1] for i in selected_indices]
        
        if panel_name == "Pasargad":
            clear_screen()
            src_inbound = pg_pick_inbound(panel_client)
            if src_inbound is None:
                continue
                
            clear_screen()
            host_idx = pg_pick_host(panel_client)
            if host_idx is None:
                continue
                
            success_count = pg_clone_countries_batch(panel_client, src_inbound, selected_nodes, host_index=host_idx)
            print(f"  {C_BLUE}{'─' * 50}{C_RESET}")
            if success_count > 0:
                print(f"  {C_GREEN}🎉 Successfully mapped {success_count} Datacenter locations!{C_RESET}")
            else:
                print(f"  {C_RED}❌ Installation failed.{C_RESET}")
            input(f"\n  Press {C_BOLD}{C_WHITE}[Enter]{C_RESET} to continue...")
            break
            
        elif panel_name == "3X-UI":
            clear_screen()
            src_inbound = x3ui_pick_inbound(panel_client)
            if src_inbound is None:
                continue
                
            success_count = x3ui_clone_countries_batch(panel_client, src_inbound, selected_nodes)
            print(f"  {C_BLUE}{'─' * 50}{C_RESET}")
            if success_count > 0:
                print(f"  {C_GREEN}🎉 Successfully mapped {success_count} Datacenter locations!{C_RESET}")
            else:
                print(f"  {C_RED}❌ Installation failed.{C_RESET}")
            input(f"\n  Press {C_BOLD}{C_WHITE}[Enter]{C_RESET} to continue...")
            break

def remove_datacenter_locations(panel_client, panel_name):
    clear_screen()
    print(f"\n{C_YELLOW}[~] Fetching Datacenter locations...{C_RESET}")
    
    dc_inbounds = []
    
    if panel_name == "Pasargad":
        config = panel_client.get_core_config()
        if not config:
            print(f"{C_RED}❌ Failed to fetch core config.{C_RESET}")
            time.sleep(2)
            return
            
        dc_tags = set()
        for ob in config.get("outbounds", []):
            if ob.get("protocol") == "socks":
                settings = ob.get("settings", {})
                if settings.get("address") == "10.0.0.1":
                    dc_tags.add(ob.get("tag"))
                    
        dc_inbounds = [ib for ib in config.get("inbounds", []) if ib.get("tag") in dc_tags]
        
    elif panel_name == "3X-UI":
        success, inbounds = panel_client.get_inbounds()
        if not success:
            print(f"{C_RED}❌ Failed to fetch inbounds.{C_RESET}")
            time.sleep(2)
            return
            
        success, settings = panel_client.get_xray_setting()
        if success and settings:
            if isinstance(settings, str):
                settings = json.loads(settings)
            xray_setting = settings.get("xraySetting", "{}")
            xray_config  = json.loads(xray_setting) if isinstance(xray_setting, str) else xray_setting
            
            dc_tags = set()
            for ob in xray_config.get("outbounds", []):
                if ob.get("protocol") == "socks" and ob.get("settings", {}).get("servers"):
                    servers = ob.get("settings", {}).get("servers", [])
                    if servers and servers[0].get("address") == "10.0.0.1":
                        dc_tags.add(ob.get("tag"))
            
            dc_country_names = [tag.replace("Datacenter-", "") for tag in dc_tags if tag.startswith("Datacenter-")]
            for ib in inbounds:
                remark = ib.get("remark", "")

                if any(name in remark for name in dc_country_names):

                    ib["tag"] = remark
                    dc_inbounds.append(ib)

    if not dc_inbounds:
        print(f"{C_YELLOW}📦 No Datacenter locations found in {panel_name}.{C_RESET}")
        input(f"\nPress {C_BOLD}{C_WHITE}[Enter]{C_RESET} to return...")
        return
        
    while True:
        clear_screen()
        b = "\033[96m"
        t = "\033[97m"
        x = "\033[0m"
        print(f"\n  {b}╭──────────────────────────────────────────────────╮{x}")
        print(f"  {b}│{x}{' ' * 17}\033[91mRemove Locations\033[0m{' ' * 17}{b}│{x}")
        print(f"  {b}├──────┬────────────────────────────────┬──────────┤{x}")
        print(f"  {b}│{x} \033[1mOpt.\033[0m {b}│{x} \033[1mLocation\033[0m                       {b}│{x} \033[1mPort\033[0m     {b}│{x}")
        print(f"  {b}├──────┼────────────────────────────────┼──────────┤{x}")
        for idx, ib in enumerate(dc_inbounds, 1):
            tag = ib.get("tag", "Unknown")

            name = re.sub(r"^[\U0001F1E0-\U0001F1FF\U0001F300-\U0001FAFF]+\s*", "", tag).strip() or tag
            iso = get_country_iso(name)
            loc_col = _ascii_pad(f"[{iso}] {name}", 30)
            port_col = f"{ib.get('port', 0):<8}"
            print(f"  {b}│{x} \033[91m[{idx:02d}]\033[0m {b}│{x} {t}{loc_col}{x} {b}│{x} \033[96m{port_col}\033[0m {b}│{x}")
        print(f"  {b}├──────┴────────────────────────────────┴──────────┤{x}")
        print(f"  {b}│{x} \033[97m0. Back\033[0m                                          {b}│{x}")
        print(f"  {b}╰──────────────────────────────────────────────────╯{x}\n")
        
        inp = input(f"  \033[96m>\033[0m Select node(s) to delete (e.g. 1-3,5): ").strip()
        if inp in ("0", ""):
            break
            
        sel = parse_selection(inp, len(dc_inbounds))
        if not sel:
            print(f"{C_RED}❌ Invalid selection.{C_RESET}")
            time.sleep(1.5)
            continue
            
        sel_inbounds = [dc_inbounds[i - 1] for i in sel]
        
        print(f"\n{C_RED}⚡ Deleting {len(sel_inbounds)} locations...{C_RESET}")
        print(f"  {C_BLUE}{'─' * 50}{C_RESET}")
        
        sel_countries = []
        for ib in sel_inbounds:
            tag = ib.get("tag", "")
            parts = tag.split(" ", 1)
            flag = parts[0] if len(parts) > 1 else "🌐"
            name = parts[1] if len(parts) > 1 else tag
            
            sel_countries.append({
                "name": tag.replace(flag + " ", ""),
                "in_port": ib.get("port"),
                "flag": flag
            })
            
        if panel_name == "Pasargad":
            removed = pg_execute_deletion(panel_client, sel_countries)
        else:
            removed = x3ui_execute_deletion(panel_client, sel_countries)
            
        print(f"  {C_BLUE}{'─' * 50}{C_RESET}")
        
        if removed > 0:
            print(f"  {C_GREEN}🎉 {removed} config(s) removed!{C_RESET}")
        else:
            print(f"  {C_YELLOW}Nothing to remove.{C_RESET}")
            
        input(f"\n  Press {C_BOLD}{C_WHITE}[Enter]{C_RESET} to continue...")
        break

def menu_panel_setup(token, api_request_func):
    clear_screen()
    
    panel_name = select_panel()
    if not panel_name:
        return
        
    if panel_name not in ["3X-UI", "Pasargad"]:
        print_error(f"Setup for {panel_name} is not fully supported yet.")
        time.sleep(2)
        return
        
    b = "\033[96m"
    t = "\033[97m"
    x = "\033[0m"
    
    def _print_login_header(name):
        title = f"Login to {name} Panel"
        pad = max(0, 50 - len(title))
        l1 = pad // 2
        r1 = pad - l1
        print(f"\n  {b}╭──────────────────────────────────────────────────╮{x}")
        print(f"  {b}│{x}{' ' * l1}{t}{title}{x}{' ' * r1}{b}│{x}")
        print(f"  {b}╰──────────────────────────────────────────────────╯{x}\n")
        
    client = None

    if panel_name == "3X-UI":
        with loading(f"Loading {panel_name}..."):
            client = x3ui_auto_client()
        if not client:
            if not x3ui_load_cached_creds():
                _print_login_header(panel_name)
            url, user, pw = x3ui_resolve_credentials()
            client = ThreeXUIClient(url, user, pw)
    elif panel_name == "Pasargad":
        has_cache = pg_load_cached_creds()
        if not has_cache:
            _print_login_header(panel_name)
        url, user, pw = pg_resolve_credentials()
        client = PasarGuardAPI(url, user, pw)
        
    if hasattr(client, 'api_token') and client.api_token:
        pass
    else:
        with loading("Signing in to panel..."):
            login_res = client.login()

        ok = login_res[0] if isinstance(login_res, tuple) else bool(login_res)
        if not ok:
            print(f"  \033[91m[-] Login failed. Check credentials.\033[0m")
            if panel_name == "3X-UI" and os.path.exists(X3UI_CREDS_FILE):
                os.remove(X3UI_CREDS_FILE)
            elif panel_name == "Pasargad" and os.path.exists(PG_CREDS_FILE):
                os.remove(PG_CREDS_FILE)
            time.sleep(2)
            return
    
    while True:
        clear_screen()
        title_str = f"Setup Panel: {panel_name}"
        pad = max(0, 50 - len(title_str))
        l1 = pad // 2
        r1 = pad - l1
        
        def opt(text, color):
            return f"  {b}│{x} {color}{text}\033[0m{' ' * (49 - len(text))}{b}│{x}"
            
        print(f"\n  {b}╭──────────────────────────────────────────────────╮{x}")
        print(f"  {b}│{x}{' ' * l1}{t}{title_str}{x}{' ' * r1}{b}│{x}")
        print(f"  {b}├──────────────────────────────────────────────────┤{x}")
        print(opt("1. Install Locations", "\033[92m"))
        print(opt("2. Remove Locations", "\033[91m"))
        if panel_name != "3X-UI":
            print(opt("3. Logout", "\033[93m"))
        print(opt("0. Back", "\033[97m"))
        print(f"  {b}╰──────────────────────────────────────────────────╯{x}\n")
        
        choice = input("\033[96m>\033[0m ").strip()
        
        if choice == "0" or choice == "":
            break
        elif choice == "1":
            data = api_request_func("/status", token)
            active_proxies = data.get('active_proxies', {}) if "error" not in data else {}
            install_datacenter_locations(client, panel_name, active_proxies)
        elif choice == "2":
            remove_datacenter_locations(client, panel_name)
        elif choice == "3" and panel_name != "3X-UI":
            print_info("Logging out from Panel...")

            if panel_name == "3X-UI":
                if os.path.exists(X3UI_CREDS_FILE):
                    os.remove(X3UI_CREDS_FILE)
            elif panel_name == "Pasargad":
                if os.path.exists(PG_CREDS_FILE):
                    os.remove(PG_CREDS_FILE)
            print_success("Panel credentials deleted.")
            time.sleep(1)
            break
        elif choice == "0":
            break


AVAILABLE_DATACENTERS = [
    "dc1.sin-kabir.ir",
    "dc2.sin-kabir.ir",
    "dc3.sin-kabir.ir",
    "dc4.sin-kabir.ir",
    "dc5.sin-kabir.ir",
]
TOKEN_FILE = "/etc/wireguard/.client_token"
DC_FILE = "/etc/wireguard/.datacenter_domain"
WG_CONF_PATH = "/etc/wireguard/wg0.conf"

FAILOVER_INTERVAL_SEC = 60
FAILOVER_SERVICE = "t-sin-failover.service"
FAILOVER_UNIT_PATH = f"/etc/systemd/system/{FAILOVER_SERVICE}"

def dc_display_name(dc):
    try:
        return f"Datacenter {AVAILABLE_DATACENTERS.index(dc) + 1}"
    except ValueError:
        return "Datacenter"

def get_active_dc():
    if os.path.exists(DC_FILE):
        with open(DC_FILE, "r") as f:
            return f.read().strip()
    return None

def set_active_dc(domain):
    os.makedirs("/etc/wireguard", exist_ok=True)
    with open(DC_FILE, "w") as f:
        f.write(domain.strip())

def rewrite_wg_endpoint(config_text, endpoint_host):

    if not config_text or not endpoint_host:
        return config_text
    host = endpoint_host.strip()
    new_text, n = re.subn(
        r"(?im)^(\s*Endpoint\s*=\s*)([^:\s]+):(\d+)\s*$",
        lambda m: f"{m.group(1)}{host}:{m.group(3)}",
        config_text,
    )
    return new_text if n else config_text

def ensure_wg_endpoint_uses_domain():

    dc = get_active_dc()
    if not dc or not os.path.exists(WG_CONF_PATH):
        return False
    try:
        with open(WG_CONF_PATH, "r", encoding="utf-8") as f:
            conf = f.read()
    except Exception:
        return False

    m = re.search(r"(?im)^\s*Endpoint\s*=\s*([^:\s]+):(\d+)\s*$", conf)
    if not m:
        return False
    current_host = m.group(1).strip()
    if current_host.lower() == dc.lower():
        return False

    new_conf = rewrite_wg_endpoint(conf, dc)
    if new_conf == conf:
        return False
    try:
        with open(WG_CONF_PATH, "w", encoding="utf-8") as f:
            f.write(new_conf)
        _run("systemctl restart wg-quick@wg0", check=False)
        return True
    except Exception:
        return False

def _ping_ms(host):
    ping_res = ping_host(host)
    try:
        return float(ping_res.replace("ms", ""))
    except ValueError:
        return None

def get_best_datacenter():
    best_dc = None
    best_ping = float('inf')
    
    print("\n  \033[96mFinding the best route...\033[0m")
    for dc in AVAILABLE_DATACENTERS:
        ping_val = _ping_ms(dc)
        if ping_val is not None and ping_val < best_ping:
            best_ping = ping_val
            best_dc = dc
            
    if best_dc:
        print(f"\n  \033[92mBest ping: {dc_display_name(best_dc)}\033[0m")
        time.sleep(1)
        return best_dc
    print(f"\n  \033[93mCould not ping any datacenter. Defaulting to Datacenter 1\033[0m")
    time.sleep(1)
    return AVAILABLE_DATACENTERS[0]

def rank_working_datacenters(token):

    ranked = []
    for dc in AVAILABLE_DATACENTERS:
        ping_val = _ping_ms(dc)
        if ping_val is None:
            continue
        status = api_request("/status", token, override_dc=dc, timeout=6)
        if "error" in status:
            continue
        ranked.append((dc, ping_val))
    ranked.sort(key=lambda x: x[1])
    return ranked

def ensure_datacenter_connection(token, quiet=False):

    if not token:
        return False

    current = get_active_dc()
    if current:
        st = api_request("/status", token, override_dc=current, timeout=6)
        if "error" not in st:

            if ensure_wg_endpoint_uses_domain() and not quiet:
                print(f"  \033[92mWireGuard endpoint updated → {current}\033[0m")
            wg_up = subprocess.run(
                "systemctl is-active --quiet wg-quick@wg0", shell=True
            ).returncode == 0
            if wg_up:
                return True
            if not quiet:
                print(f"  \033[93mWireGuard down — re-registering on {dc_display_name(current)}...\033[0m")
            return bool(menu_install(token, prefer_dc=current, quiet=quiet))

    if not quiet:
        print(f"\n  \033[93mCurrent datacenter unavailable. Searching for a working route...\033[0m")

    ranked = rank_working_datacenters(token)
    if not ranked:
        if not quiet:
            print(f"  \033[91mNo datacenter accepts this token right now.\033[0m")
        return False


    for dc, _ping in ranked:
        if current and dc != current:
            api_request("/disconnect", token, override_dc=current, timeout=4)
        if menu_install(token, prefer_dc=dc, quiet=quiet):
            if not quiet:
                print(f"  \033[92mFailover → {dc_display_name(dc)}\033[0m")
            return True
    return False

def install_failover_service():

    script_path = os.path.abspath(__file__)
    unit = f"""[Unit]
Description=T.Sin datacenter failover watcher
After=network-online.target wg-quick@wg0.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 {script_path} --failover-daemon
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
"""
    try:
        with open(FAILOVER_UNIT_PATH, "w") as f:
            f.write(unit)
        _run("systemctl daemon-reload", check=False)
        _run(f"systemctl enable --now {FAILOVER_SERVICE}", check=False)
    except Exception:
        pass

def run_failover_daemon():
    while True:
        try:
            token = get_saved_token()
            if token:

                ensure_wg_endpoint_uses_domain()
                ensure_datacenter_connection(token, quiet=True)
        except Exception:
            pass
        time.sleep(FAILOVER_INTERVAL_SEC)

def _run(cmd, check=True):
    try:
        subprocess.run(cmd, shell=True, check=check, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def check_root():
    if os.geteuid() != 0:
        print("\033[91mThis script must be run as root (use sudo).\033[0m")
        sys.exit(1)

def ping_host(host):
    try:
        out = subprocess.check_output(f"ping -c 1 -W 1 {host}", shell=True, text=True)
        import re
        match = re.search(r'time=([\d.]+)\s*ms', out)
        if match:
            return f"{float(match.group(1)):.0f}ms"
    except Exception:
        pass
    return "Fail"

def install_dependencies():
    if not os.path.exists("/usr/bin/wg"):
        print("\033[96mInstalling WireGuard...\033[0m")
        _run("apt-get update && apt-get install -y wireguard wireguard-tools")

def get_saved_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    return None

def save_token(token):
    with open(TOKEN_FILE, "w") as f:
        f.write(token.strip())

def delete_token():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)

def shorten_token_error(err):

    e = (err or "").lower()
    if "timed out" in e or "timeout" in e:
        return "Unreachable"
    if "connection refused" in e or "connect" in e:
        return "API down"
    if "invalid token" in e:
        return "Invalid token"
    if "paused" in e:
        return "Paused"
    if "in use" in e:
        return "In use elsewhere"
    if "failed to contact master" in e:
        return "Master unreachable"
    return (err or "Fail")[:21]

def api_request(path, token, override_dc=None, timeout=12):
    domain = override_dc if override_dc else get_active_dc()
    if not domain:
        return {"error": "No datacenter selected"}
    url = f"http://{domain}:8080{path}?token={token}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8')
        try:
            return {"error": json.loads(err_msg).get('error', err_msg)}
        except Exception:
            return {"error": f"HTTP {e.code}"}
    except Exception as e:
        err = str(e)
        if "timed out" in err.lower() or "timeout" in err.lower():
            return {"error": "Unreachable (port 8080 timeout)"}
        if "refused" in err.lower():
            return {"error": "API down (connection refused)"}
        return {"error": err}

def setup_wireguard(config_text, endpoint_host=None):

    if endpoint_host:
        config_text = rewrite_wg_endpoint(config_text, endpoint_host)
    os.makedirs("/etc/wireguard", exist_ok=True)
    with open(WG_CONF_PATH, "w") as f:
        f.write(config_text)
    _run("systemctl enable wg-quick@wg0")
    if not _run("systemctl restart wg-quick@wg0"):
        return False
    return True

def clear_screen():
    os.system("clear")

class AppLoader:

    _FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(self):
        self._stop = threading.Event()
        self._msg = "Loading..."
        self._lock = threading.Lock()
        self._thr = None

    def start(self, message="Loading..."):
        with self._lock:
            self._msg = message
        self._stop.clear()
        if self._thr and self._thr.is_alive():
            return self
        self._thr = threading.Thread(target=self._run, daemon=True)
        self._thr.start()
        return self

    def update(self, message):
        with self._lock:
            self._msg = message

    def stop(self):
        self._stop.set()
        if self._thr:
            self._thr.join(timeout=1.5)
            self._thr = None
        try:
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()
        except Exception:
            pass

    def _run(self):
        i = 0
        b, t, x = "\033[96m", "\033[97m", "\033[0m"
        dim = "\033[90m"
        try:
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()
        except Exception:
            pass
        while not self._stop.is_set():
            with self._lock:
                msg = (self._msg or "Loading...")[:28]
            spin = self._FRAMES[i % len(self._FRAMES)]
            i += 1
            pad = max(0, 28 - len(msg))

            out = (
                "\033[H\033[J"
                f"\n  {b}╭────────────────────────────────────╮{x}\n"
                f"  {b}│{x}       {t}T.Sin Pro Node Manager{x}       {b}│{x}\n"
                f"  {b}├────────────────────────────────────┤{x}\n"
                f"  {b}│{x}                                    {b}│{x}\n"
                f"  {b}│{x}   {b}{spin}{x}  {t}{msg}{x}{' ' * pad}  {b}│{x}\n"
                f"  {b}│{x}                                    {b}│{x}\n"
                f"  {b}│{x}           {dim}Please wait...{x}           {b}│{x}\n"
                f"  {b}╰────────────────────────────────────╯{x}\n"
            )
            try:
                sys.stdout.write(out)
                sys.stdout.flush()
            except Exception:
                break
            self._stop.wait(0.09)


@contextmanager
def loading(message="Loading..."):

    ldr = AppLoader().start(message)
    try:
        yield ldr
    finally:
        ldr.stop()

def menu_install(token=None, prefer_dc=None, quiet=False, preserve_token_on_fail=False):
    if not token:
        token = get_saved_token()
    if not token:
        if quiet:
            return False
        token = input("\n\033[96m>\033[0m Enter your Client Token: ").strip()
        if not token: return False
        
    if not quiet:
        print(f"\n  \033[96mSearching datacenters for your token...\033[0m")
    
    success_dc = None
    data = None
    last_error = None


    scan_list = [prefer_dc] if prefer_dc else list(AVAILABLE_DATACENTERS)
    
    for dc in scan_list:
        dc_name = dc_display_name(dc)
        if not quiet:
            print(f"  \033[93mTesting {dc_name}...\033[0m")

        res = api_request("/register", token, override_dc=dc, timeout=15)
        
        if "error" not in res and res.get('status') == 'success' and res.get('wg_conf'):
            success_dc = dc
            data = res
            break
        last_error = res.get("error") or "register failed"
            
    if not success_dc:
        if not quiet:
            print(f"\n\033[91m❌ Could not register on {dc_display_name(prefer_dc) if prefer_dc else 'any datacenter'}.\033[0m")
            if last_error:
                print(f"\033[93m   Reason: {last_error}\033[0m\n")

            if not prefer_dc and not preserve_token_on_fail:
                delete_token()
            input("Press Enter to continue...")
        return False
        
    set_active_dc(success_dc)
        

    if setup_wireguard(data['wg_conf'], endpoint_host=success_dc):
        save_token(token)
        if quiet:
            return True
        clear_screen()
        b = "\033[96m"
        x = "\033[0m"
        print(f"  {b}╭────────────────────────────────────╮{x}")
        print(f"  {b}│{x} \033[92mConnected to {dc_display_name(success_dc)}!\033[0m         {b}│{x}")
        print(f"  {b}╰────────────────────────────────────╯{x}\n")
        time.sleep(1.5)
        return True
    else:
        if not quiet:
            print("\n\033[91mFailed to start WireGuard interface.\033[0m")
            input("Press Enter to continue...")
        return False

def menu_update():
    clear_screen()
    b = "\033[96m"
    t = "\033[97m"
    x = "\033[0m"
    print(f"\n  {b}╭──────────────────────────────────────────────────╮{x}")
    print(f"  {b}│{x}{' ' * 22}{t}Update{x}{' ' * 22}{b}│{x}")
    print(f"  {b}├──────────────────────────────────────────────────┤{x}")
    print(f"  {b}│{x} {t}Download & install the latest T.Sin Pro from{x}     {b}│{x}")
    print(f"  {b}│{x} {t}GitHub, then relaunch automatically.{x}             {b}│{x}")
    print(f"  {b}╰──────────────────────────────────────────────────╯{x}\n")

    if not confirm_proceed("Update to the latest version now?"):
        print(f"\n  {C_YELLOW}Cancelled.{C_RESET}")
        time.sleep(1.2)
        return

    print(f"\n  {C_CYAN}[~] Fetching latest release from GitHub...{C_RESET}\n")

    install_url = "https://raw.githubusercontent.com/1NoJoom/T.Sin_Pro/main/install.sh"
    tmp_installer = "/tmp/t-sin-install.sh"
    try:
        os.execvp("bash", ["bash", "-c",
            f'curl -fsSL "{install_url}" -o "{tmp_installer}" '
            f'&& bash "{tmp_installer}"'
        ])
    except Exception as e:
        print(f"\n  {C_RED}❌ Update failed: {e}{C_RESET}")
        input("\n  Press Enter to continue...")

def menu_uninstall():
    print("\n  \033[91mAre you sure you want to logout from your token?\033[0m")
    choice = input("  Type 'y' to confirm: ").strip().lower()
    if choice == 'y':
        token = get_saved_token()
        if token:
            api_request("/disconnect", token)
        _run("systemctl stop wg-quick@wg0", check=False)
        _run("systemctl disable wg-quick@wg0", check=False)
        if os.path.exists("/etc/wireguard/wg0.conf"):
            os.remove("/etc/wireguard/wg0.conf")
        delete_token()
        print("\n\033[92mSuccessfully disconnected and uninstalled.\033[0m\n")
    else:
        print("\nCancelled.\n")
    input("Press Enter to continue...")

def menu_change_token():
    current_token = get_saved_token()
    if current_token:
        print(f"\nCurrent Token: \033[96m{current_token}\033[0m")
    else:
        print("\nNo token currently saved.")
        
    new_token = input("\nEnter new token (or press Enter to cancel): ").strip()
    if not new_token:
        return
    if current_token and new_token == current_token:
        print("\n\033[93mSame token — nothing changed.\033[0m")
        time.sleep(1.2)
        return
        

    if not menu_install(new_token, preserve_token_on_fail=True):
        return

def menu_live_status(token):
    if not token:
        print("\n\033[91mNot Logged In. Please connect first.\033[0m")
        time.sleep(2)
        return
        
    try:
        with loading("Opening live status..."):
            active_dc = get_active_dc()

            _ = api_request("/status", token)
        while True:
            dc_ping = ping_host(active_dc) if active_dc else "Fail"
            data = api_request("/status", token)
            
            b = "\033[96m"
            t = "\033[97m"
            x = "\033[0m"
            
            frame = "\033[H"
            
            if "error" in data:
                frame += f"  {b}╭──────────────────────────────────────────────────╮{x}\n"
                frame += f"  {b}│{x}  \033[91mError: {data['error'][:38]:<38}\033[0m  {b}│{x}\n"
                frame += f"  {b}╰──────────────────────────────────────────────────╯{x}\n"
                frame += "\033[J"
                sys.stdout.write(frame)
                sys.stdout.flush()
                import select
                i, o, e = select.select([sys.stdin], [], [], 2.0)
                if i:
                    sys.stdin.readline()
                    break
                continue
                
            c_name = data['client_name'][:28]
            conn_count = data['active_connections']
            
            curr_gb = float(data.get('data_used_gb') or 0)
            try:
                limit_gb = float(data.get('data_limit_gb'))
            except (TypeError, ValueError):
                limit_gb = 0.0
            live_mbps = data.get('live_mbps', 0.0)
            
            def format_size(gb_val):
                if gb_val >= 1000:
                    return f"{gb_val/1000:.1f}T".replace(".0T", "T")
                return f"{gb_val:.1f}G".replace(".0G", "G")
                

            if limit_gb <= 0:
                data_str = f"{format_size(curr_gb)} / ∞"
            else:
                data_str = f"{format_size(curr_gb)} / {format_size(limit_gb)}"
                
            exp_str, exp_color = format_license_remaining(data.get("expiry_date"))

            exp_plain = exp_str
            exp_display = f"{exp_color}{exp_str}\033[0m"
                
            frame += f"  {b}╭──────────────────────────────────────────────────╮{x}\n"
            frame += f"  {b}│{x}       {t}             Live Status{x}                   {b}│{x}\n"
            frame += f"  {b}├──────────────────────────────────────────────────┤{x}\n"
            
            def row(label, val, val_raw_len):
                pad = max(0, 50 - 2 - len(label) - val_raw_len)
                return f"  {b}│{x} {t}{label}{x} {val}{' ' * pad}{b}│{x}\n"
                
            frame += row("Client:", f"\033[92m{c_name}\033[0m", len(c_name))
            frame += row("Usage:", f"\033[93m{data_str}\033[0m", len(data_str))
            frame += row("Speed:", f"\033[96m{live_mbps:.1f} Mbps\033[0m", len(f"{live_mbps:.1f} Mbps"))
            frame += row("Connections:", f"\033[96m{conn_count}\033[0m", len(str(conn_count)))
            frame += row("Expiry Time:", exp_display, len(exp_plain))
            
            dc_ping_color = "\033[96m"
            if dc_ping == "Fail":
                dc_ping = "Offline"
                dc_ping_color = "\033[91m"
            else:
                try:
                    ping_num = float(dc_ping.replace('ms', ''))
                    if ping_num < 20:
                        dc_ping_color = "\033[92m"
                    elif ping_num < 60:
                        dc_ping_color = "\033[93m"
                    else:
                        dc_ping_color = "\033[91m"
                except ValueError:
                    pass
                    
            frame += row("DataCenter Ping:", f"{dc_ping_color}{dc_ping}\033[0m", len(str(dc_ping)))
            
            active_proxies = data.get('active_proxies', {})
            if not active_proxies:
                frame += f"  {b}├──────────────────────────────────────────────────┤{x}\n"
                frame += f"  {b}│{x} \033[91mNo Active Locations Found!{x}                       {b}│{x}\n"
                frame += f"  {b}╰──────────────────────────────────────────────────╯{x}\n"
            else:
                frame += f"  {b}├───────────────────┬────────┬────────┬────────────┤{x}\n"
                frame += f"  {b}│{x} \033[1mLocation\033[0m          {b}│{x} \033[1mPort\033[0m   {b}│{x} \033[1mPing\033[0m   {b}│{x} \033[1mLatency\033[0m    {b}│{x}\n"
                frame += f"  {b}├───────────────────┼────────┼────────┼────────────┤{x}\n"
                for port, p_data in active_proxies.items():
                    c_name_loc = p_data.get('country', 'Unknown')[:17]
                    c_ping = str(p_data.get('ping_ms', '?')) + "ms"
                    try:
                        dc_ping_val = float(dc_ping.replace('ms', ''))
                        target_ping_val = float(str(p_data.get('ping_ms', '0')))
                        total_ping_str = f"{dc_ping_val + target_ping_val:.0f}ms"
                    except ValueError:
                        total_ping_str = "?"
                        
                    col1 = f" {c_name_loc:<17} "
                    col2 = f" {port:<6} "
                    col3 = f" {c_ping:<6} "
                    col4 = f" {total_ping_str:<10} "
                    frame += f"  {b}│{x}\033[96m{col1}\033[0m{b}│{x}\033[93m{col2}\033[0m{b}│{x}\033[92m{col3}\033[0m{b}│{x}\033[92m{col4}\033[0m{b}│{x}\n"
                frame += f"  {b}╰───────────────────┴────────┴────────┴────────────╯{x}\n"
                
            frame += f"\n  {t}Press [Enter] to return to main menu...{x}\n"
            frame += "\033[J" 
            sys.stdout.write(frame)
            sys.stdout.flush()
            
            import select
            i, o, e = select.select([sys.stdin], [], [], 2.0)
            if i:
                sys.stdin.readline()
                break
    except KeyboardInterrupt:
        return

def menu_datacenters(token):
    b = "\033[96m"
    t = "\033[97m"
    x = "\033[0m"
    

    results = []
    with loading("Scanning datacenters...") as ldr:
        opt = 0
        for dc in AVAILABLE_DATACENTERS:
            ldr.update(f"Checking {dc_display_name(dc)}...")
            ping_val = ping_host(dc)
            if ping_val == "Fail":
                continue
            token_ok = True
            err_msg = None
            if token:
                status = api_request("/status", token, override_dc=dc)
                if "error" in status:
                    token_ok = False
                    err_msg = str(status.get("error") or "Unknown error")
            opt += 1
            results.append((opt, dc, ping_val, token_ok, err_msg))
        
    clear_screen()
    current_dc = get_active_dc()

    if not results:
        print(f"\n  {b}╭──────────────────────────────────────────────────────────────╮{x}")
        print(f"  {b}│{x}                      {t}Change Datacenter{x}                       {b}│{x}")
        print(f"  {b}╰──────────────────────────────────────────────────────────────╯{x}\n")
        print(f"  \033[91mNo online datacenters found.\033[0m")
        input("\n  Press Enter to continue...")
        return
    
    print(f"\n  {b}╭──────────────────────────────────────────────────────────────╮{x}")
    print(f"  {b}│{x}                      {t}Change Datacenter{x}                       {b}│{x}")
    print(f"  {b}├────────┬──────────────────┬──────────┬───────────────────────┤{x}")
    print(f"  {b}│{x} \033[1mOption\033[0m {b}│{x} \033[1mDatacenter\033[0m       {b}│{x} \033[1mPing\033[0m     {b}│{x} \033[1mToken\033[0m                 {b}│{x}")
    print(f"  {b}├────────┼──────────────────┼──────────┼───────────────────────┤{x}")
    
    for idx, dc, ping_val, token_ok, err_msg in results:
        active_mark = "★" if dc == current_dc else " "
        col1 = f" {idx}. {active_mark}"
        dc_name = dc_display_name(dc)
        col2 = f" {dc_name:<16} "
        
        try:
            ping_num = float(ping_val.replace('ms', ''))
            if ping_num < 20:
                ping_color = "\033[92m" 
            elif ping_num < 60:
                ping_color = "\033[93m"
            else:
                ping_color = "\033[91m"
            ping_text = f"{ping_num:.0f}ms"
        except ValueError:
            ping_color = "\033[91m"
            ping_text = "Offline"
            
        col3 = f" {ping_text:<8} "
        if token_ok:
            tok_color = "\033[92m"
            tok_text = "OK"
        else:
            tok_color = "\033[91m"
            tok_text = shorten_token_error(err_msg)
        col4 = f" {tok_text:<21} "
        
        color = "\033[92m" if dc == current_dc else "\033[97m"
        print(f"  {b}│{x}{color}{col1:<8}\033[0m{b}│{x}{color}{col2}\033[0m{b}│{x}{ping_color}{col3}\033[0m{b}│{x}{tok_color}{col4}\033[0m{b}│{x}")
        
    print(f"  {b}╰────────┴──────────────────┴──────────┴───────────────────────╯{x}\n")
    print(f"  {t}Enter option number to switch, or press Enter to cancel.{x}\n")
    
    choice = input("\033[96m>\033[0m ").strip()
    if not choice.isdigit():
        return
        
    choice_val = int(choice)
    
    selected_result = None
    for res in results:
        if res[0] == choice_val:
            selected_result = res
            break
            
    if selected_result:
        _, new_dc, ping_val, token_ok, err_msg = selected_result

        if not token_ok:
            print(f"\n  \033[91m{dc_display_name(new_dc)} rejected token:\033[0m")
            print(f"  \033[93m{err_msg}\033[0m")
            input("\n  Press Enter to continue...")
            return
            
        if new_dc == current_dc:
            print(f"\n  \033[93m{dc_display_name(new_dc)} is already active.\033[0m")
            time.sleep(1.5)
            return
            
        print(f"\n  \033[96mSwitching to {dc_display_name(new_dc)}...\033[0m")


        if token and current_dc:
            api_request("/disconnect", token, override_dc=current_dc, timeout=5)

        set_active_dc(new_dc)
        
        if token:
            print(f"  \033[96mRe-registering with {dc_display_name(new_dc)}...\033[0m")
            if not menu_install(token, prefer_dc=new_dc):

                if current_dc:
                    set_active_dc(current_dc)
                print(f"  \033[91mFailed to register with {dc_display_name(new_dc)}.\033[0m")
                time.sleep(2)

def _ensure_tty_stdin():

    try:
        if sys.stdin and sys.stdin.isatty():
            return
    except Exception:
        pass
    try:
        sys.stdin = open("/dev/tty", "r")
    except Exception:
        pass

def main():
    _ensure_tty_stdin()
    check_root()
    with loading("Checking dependencies...") as ldr:
        install_dependencies()
        ldr.update("Preparing services...")
        install_failover_service()
    
    while True:
        token = get_saved_token()
        while not token:
            clear_screen()
            b = "\033[96m"
            t = "\033[97m"
            x = "\033[0m"
            print(f"\n  {b}╭────────────────────────────────────╮{x}")
            print(f"  {b}│{x}       {t}T.Sin Pro Node Manager{x}       {b}│{x}")
            print(f"  {b}├────────────────────────────────────┤{x}")
            print(f"  {b}│{x} \033[93mPlease enter your connection token\033[0m {b}│{x}")
            print(f"  {b}╰────────────────────────────────────╯{x}\n")
            try:
                entered_token = input(f"  {t}> Token:{x} ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n")
                sys.exit(0)
                
            if not entered_token:
                print("\n  \033[93mExiting...\033[0m\n")
                sys.exit(0)
                
            if not menu_install(entered_token):
                print("\n  \033[91m❌ Invalid token or setup failed! Please try again.\033[0m")
                time.sleep(2)
            else:
                token = get_saved_token()


        with loading("Connecting to datacenter...") as ldr:
            ok = ensure_datacenter_connection(token, quiet=True)
            if not ok:
                data = {"error": "datacenter unavailable"}
            else:
                ldr.update("Loading account...")
                token = get_saved_token()
                data = api_request("/status", token) if token else {"error": "no token"}

        if not ok or "error" in data:

            delete_token()
            if os.path.exists(DC_FILE):
                try:
                    os.remove(DC_FILE)
                except Exception:
                    pass
            _run("systemctl stop wg-quick@wg0", check=False)
            token = None
            continue

        token = get_saved_token()
        if not token:
            continue
                
        clear_screen()
        
        b = "\033[96m"
        t = "\033[97m"
        x = "\033[0m"
        
        if "error" not in data:
            client_name = data.get('client_name', 'Unknown')
            try:
                limit_gb = float(data.get('data_limit_gb'))
            except (TypeError, ValueError):
                limit_gb = 0.0
            curr_gb = float(data.get('data_used_gb') or 0)
            
            exp_str, exp_color = format_license_remaining(data.get("expiry_date"))
                
            def format_size(gb_val):
                if gb_val >= 1000:
                    return f"{gb_val/1000:.1f}T".replace(".0T", "T")
                return f"{gb_val:.1f}G".replace(".0G", "G")
                
            data_color = t

            if limit_gb <= 0:
                data_str = f"{format_size(curr_gb)}/∞"
            else:
                data_str = f"{format_size(curr_gb)}/{format_size(limit_gb)}"
                if curr_gb >= limit_gb:
                    data_color = "\033[91m"
                elif curr_gb >= (limit_gb / 2):
                    data_color = "\033[93m"
        else:
            client_name = "Unknown"
            exp_str = "N/A"
            exp_color = t
            data_str = f"Invalid License ({data.get('error','')})"
            data_color = "\033[91m"
            
        print(f"  {b}╭──────────────────────────────────────────────────╮{x}")
        print(f"  {b}│{x} {b}       ████████╗    ███████╗██╗███╗   ██╗        {x}{b}│{x}")
        print(f"  {b}│{x} {b}       ╚══██╔══╝    ██╔════╝██║████╗  ██║        {x}{b}│{x}")
        print(f"  {b}│{x} {b}          ██║       ███████╗██║██╔██╗ ██║        {x}{b}│{x}")
        print(f"  {b}│{x} {b}          ██║       ╚════██║██║██║╚██╗██║        {x}{b}│{x}")
        print(f"  {b}│{x} {b}          ██║  ██╗  ███████║██║██║ ╚████║        {x}{b}│{x}")
        print(f"  {b}│{x} {b}          ╚═╝  ╚═╝  ╚══════╝╚═╝╚═╝  ╚═══╝        {x}{b}│{x}")
        print(f"  {b}│{x}              {t}T.Sin Pro Node Manager{x}              {b}│{x}")
        
        c_name = client_name[:15]
        left_1 = f" User: {c_name}"
        left_1 += " " * max(0, 24 - len(left_1))
        
        right_1 = f" Ver: 1.0"
        right_1 += " " * max(0, 25 - len(right_1))
        
        if exp_str.endswith("Minutes"):
            exp_str = exp_str.replace("Minutes", "Mins")
            
        raw_left_2 = f" Exp: {exp_str}"
        pad_l2 = max(0, 24 - len(raw_left_2))
        left_2 = f" Exp: {exp_color}{exp_str}{t}{' ' * pad_l2}"
        
        raw_val = data_str
        raw_right_2 = f" Usage: {raw_val}"
        if len(raw_right_2) > 25:
            raw_val = raw_val[:16] + "…"
            raw_right_2 = f" Usage: {raw_val}"
        pad_r2 = max(0, 25 - len(raw_right_2))
        right_2 = f" Usage: {data_color}{raw_val}{t}{' ' * pad_r2}"
        
        print(f"  {b}├────────────────────────┬─────────────────────────┤{x}")
        print(f"  {b}│{x}{t}{left_1}{x}{b}│{x}{t}{right_1}{x}{b}│{x}")
        print(f"  {b}├────────────────────────┼─────────────────────────┤{x}")
        print(f"  {b}│{x}{t}{left_2}{x}{b}│{x}{t}{right_2}{x}{b}│{x}")
        print(f"  {b}├────────────────────────┴─────────────────────────┤{x}")
        
        def opt(text):
            return f"  {b}│{x} {t}{text}{x}{' ' * (49 - len(text))}{b}│{x}"
            
        print(opt("[1] Panel Setup"))
        print(opt("[2] Update"))
        print(opt("[3] Live Status"))
        print(opt("[4] Change Datacenter"))
        print(opt("[5] Change License"))
        print(opt("[6] Logout"))
        print(opt("[0] Exit"))
        print(f"  {b}╰──────────────────────────────────────────────────╯{x}\n")
        
        try:
            choice = input("\033[96m>\033[0m ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n")
            sys.exit(0)
        
        if choice == "1":
            with loading("Checking connection..."):
                ensure_datacenter_connection(token, quiet=True)
            token = get_saved_token()
            menu_panel_setup(token, api_request)
        elif choice == "2":
            menu_update()
        elif choice == "3":
            with loading("Checking connection..."):
                ensure_datacenter_connection(token, quiet=True)
            token = get_saved_token()
            menu_live_status(token)
        elif choice == "4":
            with loading("Checking connection..."):
                ensure_datacenter_connection(token, quiet=True)
            token = get_saved_token()
            menu_datacenters(token)
        elif choice == "5":
            menu_change_token()
        elif choice == "6":
            menu_uninstall()
        elif choice == "0":
            sys.exit(0)

def create_shortcut():
    if os.name == "posix":
        shortcut_path = "/usr/local/bin/T.Sin"
        script_path = os.path.abspath(__file__)
        if not os.path.exists(shortcut_path):
            try:
                with open(shortcut_path, "w") as f:
                    f.write(f"#!/bin/bash\npython3 {script_path} \"$@\"\n")
                os.chmod(shortcut_path, 0o755)
            except Exception:
                pass

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--failover-daemon":
        check_root()
        run_failover_daemon()
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--failover-once":
        check_root()
        tok = get_saved_token()
        ok = ensure_datacenter_connection(tok, quiet=False) if tok else False
        sys.exit(0 if ok else 1)
    create_shortcut()
    main()
