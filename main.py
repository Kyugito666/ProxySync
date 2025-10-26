print("DEBUG: Starting main.py execution", flush=True)
import os
import random
import shutil
import time
import re
import sys
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import ui  # Mengimpor semua fungsi UI dari file ui.py

# --- Konfigurasi ---
PROXYLIST_SOURCE_FILE = "proxylist.txt"
PROXY_SOURCE_FILE = "proxy.txt"
PATHS_SOURCE_FILE = "paths.txt"
APILIST_SOURCE_FILE = "apilist.txt"
FAIL_PROXY_FILE = "fail_proxy.txt"
SUCCESS_PROXY_FILE = "success_proxy.txt"
PROXY_BACKUP_FILE = "proxy_backup.txt"
WEBSHARE_APIKEYS_FILE = "apikeys.txt"

# --- Konfigurasi Webshare (BARU) ---
WEBSHARE_AUTH_URL = "https://proxy.webshare.io/api/v2/proxy/ipauthorization/"
WEBSHARE_SUB_URL = "https://proxy.webshare.io/api/v2/subscription/"
WEBSHARE_CONFIG_URL = "https://proxy.webshare.io/api/v2/proxy/config/" # <-- BARU
WEBSHARE_DOWNLOAD_URL_FORMAT = "https://proxy.webshare.io/api/v2/proxy/list/download/{token}/-/any/{username}/direct/-/?plan_id={plan_id}" # <-- BARU
IP_CHECK_SERVICE_URL = "https://api.ipify.org?format=json"
# --- AKHIR KONFIGURASI BARU ---

# --- PERUBAHAN UTAMA UNTUK TES PROXY ---
PROXY_TIMEOUT = 20
MAX_WORKERS = 15
CHECK_URLS = ["https://api.ipify.org", "http://httpbin.org/ip"]
# --- AKHIR PERUBAHAN ---

API_DOWNLOAD_WORKERS = 1
RETRY_COUNT = 2

# --- FUNGSI LOGIKA INTI ---

# --- Fungsi Utility ---
def load_github_token(file_path):
    global GITHUB_TEST_TOKEN
    try:
        if not os.path.exists(file_path): ui.console.print(f"[bold red]Error: '{file_path}' tidak ada.[/bold red]"); return False
        with open(file_path, "r") as f: lines = f.readlines()
        if len(lines) < 3: ui.console.print(f"[bold red]Error: Format '{file_path}' salah.[/bold red]"); return False
        first_token = lines[2].strip().split(',')[0].strip()
        if not first_token or not (first_token.startswith("ghp_") or first_token.startswith("github_pat_")): ui.console.print(f"[bold red]Error: Token awal '{file_path}' invalid.[/bold red]"); return False
        GITHUB_TEST_TOKEN = first_token
        ui.console.print(f"[green]✓ Token GitHub OK.[/green]"); return True
    except Exception as e: ui.console.print(f"[bold red]Gagal load token GitHub: {e}[/bold red]"); return False

def load_apis(file_path):
    if not os.path.exists(file_path):
        with open(file_path, "w") as f: f.write("# URL API manual, 1 per baris\n"); return []
    with open(file_path, "r") as f: return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

def load_webshare_apikeys(file_path):
    if not os.path.exists(file_path):
        with open(file_path, "w") as f: f.write("# API key Webshare, 1 per baris\n")
        ui.console.print(f"[yellow]'{file_path}' dibuat. Isi API key.[/yellow]"); return []
    with open(file_path, "r") as f: return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

def get_current_public_ip():
    ui.console.print("1. Cek IP publik...")
    try:
        response = requests.get(IP_CHECK_SERVICE_URL, timeout=WEBSHARE_API_TIMEOUT)
        response.raise_for_status(); new_ip = response.json()["ip"]
        ui.console.print(f"   -> [bold green]IP baru: {new_ip}[/bold green]"); return new_ip
    except requests.RequestException as e: ui.console.print(f"   -> [bold red]ERROR Gagal cek IP: {e}[/bold red]", file=sys.stderr); return None

def get_account_email(session: requests.Session) -> str:
    try:
        response = session.get(WEBSHARE_PROFILE_URL, timeout=WEBSHARE_API_TIMEOUT)
        if response.status_code == 401: return "[bold red]API Key Invalid[/]"
        response.raise_for_status()
        data = response.json(); email = data.get("email")
        if email: return email
        else: return "[yellow]Email N/A[/]"
    except requests.exceptions.HTTPError as e: return f"[bold red]HTTP Err ({e.response.status_code})[/]"
    except requests.RequestException: return "[bold red]Koneksi Err[/]"
    except Exception: return "[bold red]Parsing Err[/]"

def get_target_plan_id(session: requests.Session):
    ui.console.print("2. Cek Plan ID (via /config/)...")
    try:
        response = session.get(WEBSHARE_CONFIG_URL, timeout=WEBSHARE_API_TIMEOUT)
        if response.status_code == 401: ui.console.print("   -> [bold red]ERROR: API Key invalid.[/bold red]"); return None
        response.raise_for_status()
        data = response.json(); plan_id = data.get("id")
        if plan_id: plan_id_str = str(plan_id); ui.console.print(f"   -> [green]OK: Plan ID: {plan_id_str}[/green]"); return plan_id_str
        else: ui.console.print("   -> [bold red]ERROR: /config/ tidak return 'id'.[/bold red]"); return None
    except requests.exceptions.HTTPError as e: ui.console.print(f"   -> [bold red]ERROR HTTP: {e.response.text}[/bold red]"); return None
    except requests.RequestException as e: ui.console.print(f"   -> [bold red]ERROR Koneksi: {e}[/bold red]"); return None

def get_authorized_ips(session: requests.Session, plan_id: str):
    ui.console.print("3. Cek IP terdaftar...")
    params = {"plan_id": plan_id}; ip_to_id_map = {}
    try:
        response = session.get(WEBSHARE_AUTH_URL, params=params, timeout=WEBSHARE_API_TIMEOUT)
        response.raise_for_status(); results = response.json().get("results", [])
        for item in results:
            ip = item.get("ip_address"); auth_id = item.get("id")
            if ip and auth_id: ip_to_id_map[ip] = auth_id
        if not ip_to_id_map: ui.console.print("   -> Tidak ada IP lama.")
        else: ui.console.print(f"   -> IP lama: {', '.join(ip_to_id_map.keys())}")
        return ip_to_id_map
    except requests.RequestException as e: ui.console.print(f"   -> [bold red]ERROR Gagal cek IP lama: {e}[/bold red]"); return {}

def remove_ip(session: requests.Session, ip: str, authorization_id: int, plan_id: str):
    ui.console.print(f"   -> Hapus IP lama: {ip} (ID: {authorization_id})")
    params = {"plan_id": plan_id}
    delete_url = f"{WEBSHARE_AUTH_URL}{authorization_id}/"
    try:
        response = session.delete(delete_url, params=params, timeout=WEBSHARE_API_TIMEOUT)
        if response.status_code == 204: ui.console.print(f"   -> [green]OK Hapus: {ip}[/green]")
        else:
            ui.console.print(f"   -> [bold red]ERROR Gagal hapus {ip} ({response.status_code})[/bold red]")
            try: ui.console.print(f"      {response.json()}")
            except: ui.console.print(f"      {response.text}")
            response.raise_for_status()
    except requests.RequestException as e:
        ui.console.print(f"   -> [bold red]ERROR Gagal hapus {ip}[/bold red]")
        try: ui.console.print(f"      {e.response.text}")
        except: ui.console.print(f"      {e}")

def add_ip(session: requests.Session, ip: str, plan_id: str):
    ui.console.print(f"   -> Tambah IP baru: {ip}")
    params = {"plan_id": plan_id}; payload = {"ip_address": ip}
    try:
        response = session.post(WEBSHARE_AUTH_URL, json=payload, params=params, timeout=WEBSHARE_API_TIMEOUT)
        if response.status_code == 201: ui.console.print(f"   -> [green]OK Tambah: {ip}[/green]")
        else:
            ui.console.print(f"   -> [bold red]ERROR Gagal tambah {ip} ({response.status_code})[/bold red]")
            try: ui.console.print(f"      {response.json()}")
            except: ui.console.print(f"      {response.text}")
            response.raise_for_status()
    except requests.RequestException as e:
        ui.console.print(f"   -> [bold red]ERROR Gagal tambah {ip}[/bold red]")
        try: ui.console.print(f"      {e.response.text}")
        except: ui.console.print(f"      {e}")

def run_webshare_ip_sync():
    ui.print_header()
    ui.console.print("[bold cyan]--- Sinkronisasi IP Otorisasi Webshare ---[/bold cyan]")
    api_keys = load_webshare_apikeys(WEBSHARE_APIKEYS_FILE)
    if not api_keys: ui.console.print(f"[bold red]'{WEBSHARE_APIKEYS_FILE}' kosong.[/bold red]"); return
    new_ip = get_current_public_ip()
    if not new_ip: ui.console.print("[bold red]Gagal IP. Batal.[/bold red]"); return
    ui.console.print(f"\nSinkron IP [bold]{new_ip}[/bold] ke [bold]{len(api_keys)}[/bold] akun...")

    for api_key in api_keys:
        account_email_info = "[grey]Cek email...[/]"
        try:
            with requests.Session() as email_session:
                email_session.headers.update({"Authorization": f"Token {api_key}", "Accept": "application/json"})
                account_email_info = get_account_email(email_session) # Tanpa sensor
        except Exception: account_email_info = "[bold red]Error[/]"
        ui.console.print(f"\n--- Key: [...{api_key[-6:]}] (Email: {account_email_info}) ---")

        with requests.Session() as session:
            session.headers.update({"Authorization": f"Token {api_key}", "Accept": "application/json"})
            try:
                plan_id = get_target_plan_id(session)
                if not plan_id: ui.console.print(f"   -> [bold red]Akun skip.[/bold red]"); continue
                authorized_ips_map = get_authorized_ips(session, plan_id)
                existing_ips = list(authorized_ips_map.keys())
                if new_ip in existing_ips: ui.console.print(f"   -> [green]IP baru ({new_ip}) sudah ada. Skip.[/green]"); continue
                ui.console.print("\n4. Hapus IP lama...");
                if not existing_ips: ui.console.print("   -> Tidak ada IP lama.")
                else:
                    for ip_to_delete, auth_id_to_delete in authorized_ips_map.items(): remove_ip(session, ip_to_delete, auth_id_to_delete, plan_id)
                ui.console.print("\n5. Tambah IP baru..."); add_ip(session, new_ip, plan_id)
            except Exception as e: ui.console.print(f"   -> [bold red]!!! ERROR Hapus/Tambah. Lanjut akun berikutnya.[/bold red]")
    ui.console.print("\n[bold green]✅ Sinkronisasi IP selesai.[/bold green]")

def get_webshare_download_url(session: requests.Session, plan_id: str):
    ui.console.print("   -> Get URL download (via /config/)...")
    params = {"plan_id": plan_id}
    try:
        response = session.get(WEBSHARE_CONFIG_URL, params=params, timeout=WEBSHARE_API_TIMEOUT)
        response.raise_for_status()
        data = response.json(); token = data.get("proxy_list_download_token")
        if not token: ui.console.print("   -> [bold red]ERROR: 'proxy_list_download_token' N/A.[/bold red]"); return None
        # Format URL pakai 'username' literal
        download_url = WEBSHARE_DOWNLOAD_URL_FORMAT.format(token=token, plan_id=plan_id)
        ui.console.print(f"   -> [green]OK URL download.[/green]"); return download_url
    except requests.exceptions.HTTPError as e: ui.console.print(f"   -> [bold red]ERROR Config: {e.response.text}[/bold red]"); return None
    except requests.RequestException as e: ui.console.print(f"   -> [bold red]ERROR Koneksi (config): {e}[/bold red]"); return None

def download_proxies_from_api():
    ui.print_header()
    ui.console.print("[bold cyan]--- Unduh Proksi dari API ---[/bold cyan]")
    if os.path.exists(PROXYLIST_SOURCE_FILE) and os.path.getsize(PROXYLIST_SOURCE_FILE) > 0:
        choice = ui.Prompt.ask(f"[bold yellow]'{PROXYLIST_SOURCE_FILE}' ada. Hapus?[/bold yellow]", choices=["y", "n"], default="y").lower()
        if choice == 'n': ui.console.print("[cyan]Batal.[/cyan]"); return
    try:
        with open(PROXYLIST_SOURCE_FILE, "w") as f: pass
        ui.console.print(f"[green]'{PROXYLIST_SOURCE_FILE}' siap.[/green]\n")
    except IOError as e: ui.console.print(f"[bold red]Gagal clear file: {e}[/bold red]"); return

    all_download_targets: list[tuple[str, str | None]] = []
    ui.console.print(f"[bold]Auto-Discover dari '{WEBSHARE_APIKEYS_FILE}'...[/bold]")
    api_keys = load_webshare_apikeys(WEBSHARE_APIKEYS_FILE)
    if not api_keys: ui.console.print(f"[yellow]'{WEBSHARE_APIKEYS_FILE}' kosong.[/yellow]")

    for api_key in api_keys:
        account_email_info = "[grey]Cek email...[/]"
        try:
            with requests.Session() as email_session:
                email_session.headers.update({"Authorization": f"Token {api_key}", "Accept": "application/json"})
                account_email_info = get_account_email(email_session) # Tanpa sensor
        except Exception: account_email_info = "[bold red]Error[/]"
        ui.console.print(f"\n--- Key: [...{api_key[-6:]}] (Email: {account_email_info}) ---")

        with requests.Session() as session:
            session.headers.update({"Authorization": f"Token {api_key}", "Accept": "application/json"})
            try:
                plan_id = get_target_plan_id(session)
                if not plan_id: ui.console.print(f"   -> [bold red]Akun skip.[/bold red]"); continue
                download_url = get_webshare_download_url(session, plan_id)
                if download_url: all_download_targets.append((download_url, api_key))
                else: ui.console.print("   -> [yellow]Gagal URL. Skip.[/yellow]")
            except Exception as e: ui.console.print(f"   -> [bold red]!!! FATAL: {e}[/bold red]")

    ui.console.print(f"\n[bold]Load URL manual '{APILIST_SOURCE_FILE}'...[/bold]")
    manual_urls = load_apis(APILIST_SOURCE_FILE)
    if not manual_urls: ui.console.print(f"[yellow]'{APILIST_SOURCE_FILE}' kosong.[/yellow]")
    else:
        ui.console.print(f"[green]{len(manual_urls)} URL manual.[/green]"); all_download_targets.extend([(url, None) for url in manual_urls])

    if not all_download_targets: ui.console.print("\n[bold red]Tidak ada URL API.[/bold red]"); return
    ui.console.print(f"\n[bold cyan]Siap unduh dari {len(all_download_targets)} URL...[/bold cyan]")
    all_downloaded_proxies = ui.run_sequential_api_downloads(all_download_targets)
    if not all_downloaded_proxies: ui.console.print("\n[bold yellow]Tidak ada proksi diunduh.[/bold yellow]"); return
    try:
        with open(PROXYLIST_SOURCE_FILE, "w") as f:
            for proxy in all_downloaded_proxies: f.write(proxy + "\n")
        ui.console.print(f"\n[bold green]✅ {len(all_downloaded_proxies)} proksi ke '{PROXYLIST_SOURCE_FILE}'[/bold green]")
    except IOError as e: ui.console.print(f"\n[bold red]Gagal tulis '{PROXYLIST_SOURCE_FILE}': {e}[/bold red]")


# === PERUBAHAN KONVERSI v2 ===
def convert_proxylist_to_http():
    """Konversi proxy dari proxylist.txt ke format http dan simpan ke proxy.txt."""
    if not os.path.exists(PROXYLIST_SOURCE_FILE):
        ui.console.print(f"[bold red]Error: '{PROXYLIST_SOURCE_FILE}' tidak ditemukan.[/bold red]")
        return

    try:
        with open(PROXYLIST_SOURCE_FILE, "r") as f:
            lines = f.readlines()
    except Exception as e:
        ui.console.print(f"[bold red]Gagal membaca '{PROXYLIST_SOURCE_FILE}': {e}[/bold red]")
        return

    # Bersihkan baris kosong dan komentar sebelum menghitung
    cleaned_proxies_input = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]

    if not cleaned_proxies_input:
        ui.console.print(f"[yellow]'{PROXYLIST_SOURCE_FILE}' kosong atau hanya berisi komentar.[/yellow]")
        return

    ui.console.print(f"Mengonversi {len(cleaned_proxies_input)} proksi dari '{PROXYLIST_SOURCE_FILE}'...")

    converted_proxies = []
    skipped_count = 0
    skipped_examples = [] # Untuk menampilkan contoh yang gagal

    # Regex untuk host (bisa IP v4 atau domain)
    host_pattern = r"((?:[0-9]{1,3}\.){3}[0-9]{1,3}|(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,})"
    # Regex untuk port
    port_pattern = r"[0-9]{1,5}"
    # Regex untuk user & pass (bisa mengandung karakter apa saja KECUALI '@' dan ':')
    # Modifikasi: Bolehkan ':' di password, tapi asumsi ':' terakhir sebelum port
    user_pass_pattern = r"[^@:]+" # User
    # pass_pattern = r"[^@]+" # Pass - revisi nanti

    for p in cleaned_proxies_input:
        p = p.strip()
        if not p:
            continue

        # 1. Cek format http:// atau https://
        if p.startswith("http://") or p.startswith("https://"):
            converted_proxies.append(p)
            continue

        converted = None
        # 2. Cek format user:pass@host:port (lebih prioritas karena ada '@')
        #    Regex ini mencoba menangkap user:pass, host, dan port
        match_user_pass_host_port = re.match(rf"^(?P<user_pass>.+)@(?P<host>{host_pattern}):(?P<port>{port_pattern})$", p)
        if match_user_pass_host_port:
            user_pass = match_user_pass_host_port.group("user_pass")
            host = match_user_pass_host_port.group("host")
            port = match_user_pass_host_port.group("port")
            # Cek validitas port (harus antara 1-65535)
            if 1 <= int(port) <= 65535:
                converted = f"http://{user_pass}@{host}:{port}"
            # Jika port tidak valid, akan diskip nanti

        # 3. Jika tidak ada '@', coba split pakai ':'
        if not converted:
            parts = p.split(':')
            if len(parts) == 4:
                # Asumsi ip:port:user:pass
                ip, port, user, password = parts
                # Cek apakah bagian pertama adalah IP/Host dan kedua adalah port
                if re.match(rf"^{host_pattern}$", ip) and re.match(rf"^{port_pattern}$", port):
                    if 1 <= int(port) <= 65535:
                        converted = f"http://{user}:{password}@{ip}:{port}"
            elif len(parts) == 2:
                # Asumsi ip:port
                ip, port = parts
                if re.match(rf"^{host_pattern}$", ip) and re.match(rf"^{port_pattern}$", port):
                     if 1 <= int(port) <= 65535:
                        converted = f"http://{ip}:{port}"

        # 4. Jika berhasil dikonversi, tambahkan ke list
        if converted:
            converted_proxies.append(converted)
        else:
            skipped_count += 1
            if len(skipped_examples) < 5: # Simpan 5 contoh pertama
                skipped_examples.append(p)

    # --- Laporan Hasil ---
    if skipped_count > 0:
        ui.console.print(f"[yellow]{skipped_count} baris dilewati karena format tidak dikenali/valid.[/yellow]")
        if skipped_examples:
            ui.console.print("[yellow]Contoh yang dilewati:[/yellow]")
            for ex in skipped_examples:
                ui.console.print(f"  - {ex}")

    if not converted_proxies:
        ui.console.print("[bold red]Tidak ada proksi yang berhasil dikonversi.[/bold red]")
        return

    # --- Tulis ke file proxy.txt ---
    try:
        with open(PROXY_SOURCE_FILE, "w") as f:
            for proxy in converted_proxies:
                f.write(proxy + "\n")
        
        # Kosongkan proxylist.txt
        open(PROXYLIST_SOURCE_FILE, "w").close() 
        
        ui.console.print(f"[bold green]✅ {len(converted_proxies)} proksi dikonversi dan disimpan ke '{PROXY_SOURCE_FILE}'.[/bold green]")
        ui.console.print(f"[bold cyan]'{PROXYLIST_SOURCE_FILE}' telah dikosongkan.[/bold cyan]")

    except Exception as e:
        ui.console.print(f"[bold red]Gagal menulis ke file: {e}[/bold red]")
# === AKHIR PERUBAHAN KONVERSI v2 ===


def load_and_deduplicate_proxies(file_path):
    if not os.path.exists(file_path): return []
    try:
        with open(file_path, "r") as f: proxies = [line.strip() for line in f if line.strip()]
    except Exception as e: ui.console.print(f"[bold red]Gagal baca '{file_path}': {e}[/bold red]"); return []
    unique_proxies = sorted(list(set(proxies))); duplicates_removed = len(proxies) - len(unique_proxies)
    if duplicates_removed > 0: ui.console.print(f"[yellow]Hapus {duplicates_removed} duplikat.[/yellow]")
    try:
        with open(file_path, "w") as f:
            for proxy in unique_proxies: f.write(proxy + "\n")
    except Exception as e: ui.console.print(f"[bold red]Gagal tulis '{file_path}' (dedup): {e}[/bold red]"); return proxies
    return unique_proxies

def load_paths(file_path):
    if not os.path.exists(file_path): ui.console.print(f"[bold red]'{file_path}' N/A.[/bold red]"); return []
    try:
        with open(file_path, "r") as f:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            raw_paths = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            absolute_paths = []; invalid_paths = 0
            for p in raw_paths:
                abs_p = os.path.join(project_root, p)
                if os.path.isdir(abs_p): absolute_paths.append(abs_p)
                else: invalid_paths += 1; ui.console.print(f"[yellow]Path invalid: {abs_p} ('{p}') [/yellow]")
            if invalid_paths > 0: ui.console.print(f"[yellow]{invalid_paths} path skip.[/yellow]")
            return absolute_paths
    except Exception as e: ui.console.print(f"[bold red]Gagal baca '{file_path}': {e}[/bold red]"); return []

def backup_file(file_path, backup_path):
    if os.path.exists(file_path):
        try: shutil.copy(file_path, backup_path); ui.console.print(f"[green]Backup: '{backup_path}'[/green]")
        except Exception as e: ui.console.print(f"[bold red]Gagal backup '{backup_path}': {e}[/bold red]")

def check_proxy_final(proxy):
    if GITHUB_TEST_TOKEN is None: return proxy, False, "Token GitHub?"
    proxies_dict = {"http": proxy, "https": proxy}
    headers = {'User-Agent': 'ProxySync-Tester/1.0', 'Authorization': f'Bearer {GITHUB_TEST_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    try:
        response = requests.get(GITHUB_API_TEST_URL, proxies=proxies_dict, timeout=PROXY_TIMEOUT, headers=headers)
        if response.status_code == 401: return proxy, False, "GitHub Auth (401)"
        if response.status_code == 403: return proxy, False, "GitHub Forbidden (403)"
        if response.status_code == 407: return proxy, False, "Proxy Auth (407)"
        if response.status_code == 429: return proxy, False, "GitHub Rate Limit (429)"
        response.raise_for_status()
        if response.text and len(response.text) > 5: return proxy, True, "OK"
        else: return proxy, False, "Respons GitHub?"
    except requests.exceptions.Timeout: return proxy, False, f"Timeout ({PROXY_TIMEOUT}s)"
    except requests.exceptions.ProxyError as e: reason = str(e).split(':')[-1].strip(); return proxy, False, f"Proxy Error ({reason[:30]})"
    except requests.exceptions.RequestException as e: reason = str(e.__class__.__name__); return proxy, False, f"Koneksi Gagal ({reason})"

def distribute_proxies(proxies, paths):
    if not proxies or not paths: ui.console.print("[yellow]Distribusi skip (no data).[/yellow]"); return
    ui.console.print(f"\n[cyan]Distribusi {len(proxies)} proksi ke {len(paths)} path...[/cyan]")
    project_root_abs = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    for path in paths:
        if not os.path.isdir(path): ui.console.print(f"  [yellow]✖ Skip:[/yellow] Path invalid: {path}"); continue
        file_name = "proxies.txt"; file_path = os.path.join(path, file_name)
        if not os.path.exists(file_path): file_name = "proxy.txt"; file_path = os.path.join(path, file_name)
        rel_path_display = os.path.relpath(file_path, project_root_abs)
        proxies_shuffled = random.sample(proxies, len(proxies))
        try:
            with open(file_path, "w") as f:
                for proxy in proxies_shuffled: f.write(proxy + "\n")
            ui.console.print(f"  [green]✔[/green] Tulis ke [bold]{rel_path_display}[/bold]")
        except IOError as e: ui.console.print(f"  [red]✖[/red] Gagal tulis [bold]{rel_path_display}[/bold]: {e}")

def save_good_proxies(proxies, file_path):
    try:
        with open(file_path, "w") as f:
            for proxy in proxies: f.write(proxy + "\n")
        ui.console.print(f"\n[bold green]✅ {len(proxies)} proksi valid simpan ke '{file_path}'[/bold green]")
    except IOError as e: ui.console.print(f"\n[bold red]✖ Gagal simpan '{file_path}': {e}[/bold red]")

def run_full_process():
    ui.print_header()
    if not load_github_token(GITHUB_TOKENS_FILE): ui.console.print("[bold red]Tes proxy batal (token GitHub?).[/bold red]"); return
    distribute_choice = ui.Prompt.ask("[bold yellow]Distribusi proksi valid?[/bold yellow]", choices=["y", "n"], default="y").lower()
    ui.console.print("-" * 40); ui.console.print("[bold cyan]Langkah 1: Backup & Clean...[/bold cyan]")
    backup_file(PROXY_SOURCE_FILE, PROXY_BACKUP_FILE)
    proxies = load_and_deduplicate_proxies(PROXY_SOURCE_FILE)
    if not proxies: ui.console.print("[bold red]Stop: 'proxy.txt' kosong.[/bold red]"); return
    ui.console.print(f"Siap tes {len(proxies)} proksi unik."); ui.console.print("-" * 40)
    ui.console.print("[bold cyan]Langkah 2: Tes Akurat GitHub...[/bold cyan]")
    good_proxies = ui.run_concurrent_checks_display(proxies, check_proxy_final, MAX_WORKERS, FAIL_PROXY_FILE)
    if not good_proxies: ui.console.print("[bold red]Stop: Tidak ada proksi lolos.[/bold red]"); return
    ui.console.print(f"[bold green]{len(good_proxies)} proksi lolos.[/bold green]"); ui.console.print("-" * 40)
    if distribute_choice == 'y':
        ui.console.print("[bold cyan]Langkah 3: Distribusi...[/bold cyan]")
        paths = load_paths(PATHS_SOURCE_FILE)
        if not paths: ui.console.print("[bold red]Stop: 'paths.txt' kosong/invalid.[/bold red]"); return
        distribute_proxies(good_proxies, paths); save_good_proxies(good_proxies, SUCCESS_PROXY_FILE)
    else: ui.console.print("[bold cyan]Langkah 3: Simpan proksi valid...[/bold cyan]"); save_good_proxies(good_proxies, SUCCESS_PROXY_FILE)
    ui.console.print("\n[bold green]✅ Semua selesai![/bold green]")

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    while True:
        ui.print_header(); choice = ui.display_main_menu()
        if choice == "1": run_webshare_ip_sync(); ui.Prompt.ask("\n[bold]Tekan Enter...[/bold]")
        elif choice == "2": download_proxies_from_api(); ui.Prompt.ask("\n[bold]Tekan Enter...[/bold]")
        elif choice == "3": convert_proxylist_to_http(); ui.Prompt.ask("\n[bold]Tekan Enter...[/bold]")
        elif choice == "4": run_full_process(); ui.Prompt.ask("\n[bold]Tekan Enter...[/bold]")
        elif choice == "5": ui.manage_paths_menu_display() # Placeholder
        elif choice == "6": ui.console.print("[bold cyan]Bye![/bold cyan]"); break

if __name__ == "__main__":
    main()
