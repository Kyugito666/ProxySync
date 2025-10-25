import os
import random
import shutil
import time
import re
import sys
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

def load_apis(file_path):
    """Memuat daftar URL API dari file."""
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            f.write("# Masukkan URL API Anda di sini, satu per baris\n")
        return []
    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

# --- LOGIKA WEBSHARE IP SYNC (MENU 1) ---

def load_webshare_apikeys(file_path):
    """Memuat daftar API key Webshare dari file."""
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            f.write("# Masukkan API key Webshare Anda di sini, SATU per baris\n")
        return []
    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

def get_current_public_ip():
    """Mengambil IP publik saat ini dari layanan eksternal."""
    ui.console.print("1. Mengambil IP publik saat ini...")
    try:
        response = requests.get(IP_CHECK_SERVICE_URL, timeout=10)
        response.raise_for_status()
        new_ip = response.json()["ip"]
        ui.console.print(f"   -> [bold green]IP publik baru: {new_ip}[/bold green]")
        return new_ip
    except requests.RequestException as e:
        ui.console.print(f"   -> [bold red]ERROR: Gagal mendapatkan IP publik: {e}[/bold red]", file=sys.stderr)
        return None

def get_target_plan_id(session: requests.Session):
    """Auto-discover Plan ID. Hanya mengembalikan jika TEPAT 1 plan aktif."""
    ui.console.print("2. Auto-discover Plan ID...")
    try:
        response = session.get(WEBSHARE_SUB_URL, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        plans = data.get("results", [])
        
        # --- LOGIKA DIPERBARUI: Cari plan 'active' ---
        active_plans = [p for p in plans if p.get('status', '').lower() == 'active']
        
        if len(active_plans) == 1:
            plan = active_plans[0]
            plan_id = str(plan.get('id'))
            plan_name = plan.get('plan', {}).get('name', 'N/A')
            ui.console.print(f"   -> [green]Sukses: Ditemukan 1 plan aktif: '{plan_name}' (ID: {plan_id})[/green]")
            return plan_id
        
        elif len(active_plans) == 0:
            ui.console.print("   -> [bold red]ERROR: Tidak ada subscription plan 'active' ditemukan.[/bold red]")
            return None
            
        else:
            ui.console.print(f"   -> [bold red]ERROR: Ditemukan {len(active_plans)} plan aktif. Ambiguitas.[/bold red]")
            return None

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            ui.console.print("   -> [bold red]ERROR: API Key tidak valid.[/bold red]")
        else:
            ui.console.print(f"   -> [bold red]ERROR: HTTP Error: {e}[/bold red]")
        return None
    except requests.RequestException as e:
        ui.console.print(f"   -> [bold red]ERROR: Gagal koneksi ke Webshare: {e}[/bold red]")
        return None

def get_authorized_ips(session: requests.Session, plan_id: str):
    """Mengambil semua IP yang sudah terotorisasi di Webshare."""
    ui.console.print("3. Mengambil IP terotorisasi yang ada...")
    params = {"plan_id": plan_id}
    try:
        response = session.get(WEBSHARE_AUTH_URL, params=params)
        response.raise_for_status()
        results = response.json().get("results", [])
        existing_ips = [item["ip_address"] for item in results]
        
        if not existing_ips:
            ui.console.print("   -> Tidak ada IP lama yang terotorisasi.")
        else:
            ui.console.print(f"   -> Ditemukan IP lama: {', '.join(existing_ips)}")
        return existing_ips
    except requests.RequestException as e:
        ui.console.print(f"   -> [bold red]ERROR: Gagal mengambil IP lama: {e}[/bold red]")
        return []

def remove_ip(session: requests.Session, ip: str, plan_id: str):
    """Menghapus satu IP dari otorisasi Webshare."""
    ui.console.print(f"   -> Menghapus IP lama: {ip}")
    params = {"plan_id": plan_id}
    payload = {"ip_address": ip} 
    try:
        response = session.delete(WEBSHARE_AUTH_URL, json=payload, params=params)
        if response.status_code == 204:
            ui.console.print(f"   -> [green]Sukses hapus: {ip}[/green]")
        else:
            response.raise_for_status()
    except requests.RequestException as e:
        ui.console.print(f"   -> [bold red]ERROR: Gagal hapus {ip}: {e.response.text}[/bold red]")

def add_ip(session: requests.Session, ip: str, plan_id: str):
    """Menambahkan satu IP ke otorisasi Webshare."""
    ui.console.print(f"   -> Menambahkan IP baru: {ip}")
    params = {"plan_id": plan_id}
    payload = {"ip_address": ip}
    try:
        response = session.post(WEBSHARE_AUTH_URL, json=payload, params=params)
        if response.status_code == 201:
            ui.console.print(f"   -> [green]Sukses tambah: {ip}[/green]")
        else:
            response.raise_for_status()
    except requests.RequestException as e:
        ui.console.print(f"   -> [bold red]ERROR: Gagal tambah {ip}: {e.response.text}[/bold red]")

def run_webshare_ip_sync():
    """Fungsi orkestrasi untuk sinkronisasi IP Webshare (Menu 1)."""
    ui.print_header()
    ui.console.print("[bold cyan]--- Sinkronisasi IP Otorisasi Webshare ---[/bold cyan]")
    
    api_keys = load_webshare_apikeys(WEBSHARE_APIKEYS_FILE)
    if not api_keys:
        ui.console.print(f"[bold red]File '{WEBSHARE_APIKEYS_FILE}' kosong atau tidak ditemukan.[/bold red]")
        return

    new_ip = get_current_public_ip()
    if not new_ip:
        ui.console.print("[bold red]Gagal mendapatkan IP publik. Proses dibatalkan.[/bold red]")
        return

    ui.console.print(f"\nAkan menyinkronkan IP [bold]{new_ip}[/bold] ke [bold]{len(api_keys)}[/bold] akun...")

    for api_key in api_keys:
        ui.console.print(f"\n--- Memproses API Key: [...{api_key[-6:]}] ---")
        
        with requests.Session() as session:
            session.headers.update({
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            })
            
            try:
                plan_id = get_target_plan_id(session)
                
                if not plan_id:
                    ui.console.print("   -> [yellow]Gagal menemukan plan ID. Akun dilewati.[/yellow]")
                    continue

                existing_ips = get_authorized_ips(session, plan_id)

                ui.console.print("\n4. Memeriksa IP lama untuk dihapus...")
                ips_to_delete = [ip for ip in existing_ips if ip != new_ip]
                if not ips_to_delete:
                    ui.console.print("   -> Tidak ada IP lama yang perlu dihapus.")
                else:
                    for ip in ips_to_delete:
                        remove_ip(session, ip, plan_id)

                ui.console.print("\n5. Memeriksa IP baru untuk ditambahkan...")
                if new_ip not in existing_ips:
                    add_ip(session, new_ip, plan_id)
                else:
                    ui.console.print(f"   -> IP baru ({new_ip}) sudah terotorisasi.")
            
            except Exception as e:
                ui.console.print(f"   -> [bold red]!!! FATAL ERROR untuk akun ini: {e}[/bold red]")
    
    ui.console.print("\n[bold green]✅ Proses sinkronisasi IP Webshare selesai.[/bold green]")


# --- LOGIKA BARU: WEBSHARE PROXY DOWNLOAD (MENU 2) ---

def get_webshare_download_url(session: requests.Session, plan_id: str):
    """
    Mengambil username dan download token untuk membangun URL download proxy.
    """
    ui.console.print("   -> Memanggil 'proxy/config/' untuk URL download...")
    params = {"plan_id": plan_id}
    try:
        response = session.get(WEBSHARE_CONFIG_URL, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        username = data.get("username")
        token = data.get("proxy_list_download_token")

        if not username or not token:
            ui.console.print("   -> [bold red]ERROR: 'username' atau 'proxy_list_download_token' tidak ditemukan di response.[/bold red]")
            return None

        # Membangun URL
        download_url = WEBSHARE_DOWNLOAD_URL_FORMAT.format(
            token=token,
            username=username,
            plan_id=plan_id
        )
        ui.console.print(f"   -> [green]Sukses generate URL download.[/green]")
        return download_url

    except requests.exceptions.HTTPError as e:
        ui.console.print(f"   -> [bold red]ERROR: Gagal mengambil config proxy: {e}[/bold red]")
        return None
    except requests.RequestException as e:
        ui.console.print(f"   -> [bold red]ERROR: Gagal koneksi ke Webshare (config): {e}[/bold red]")
        return None

def download_proxies_from_api():
    """
    Mengunduh proksi dari Webshare (otomatis via apikeys.txt)
    DAN dari URL manual di apilist.txt.
    """
    ui.print_header()
    ui.console.print("[bold cyan]--- Unduh Proksi dari Daftar API ---[/bold cyan]")
    
    # 1. Kosongkan file proxylist.txt
    if os.path.exists(PROXYLIST_SOURCE_FILE) and os.path.getsize(PROXYLIST_SOURCE_FILE) > 0:
        choice = ui.Prompt.ask(
            f"[bold yellow]File '{PROXYLIST_SOURCE_FILE}' berisi data. Hapus konten lama sebelum mengunduh?[/bold yellow]",
            choices=["y", "n"], default="y"
        ).lower()
        if choice == 'n':
            ui.console.print("[cyan]Operasi dibatalkan. Proksi tidak diunduh.[/cyan]")
            return
    
    try:
        with open(PROXYLIST_SOURCE_FILE, "w") as f: pass
        ui.console.print(f"[green]'{PROXYLIST_SOURCE_FILE}' telah siap untuk diisi data baru.[/green]\n")
    except IOError as e:
        ui.console.print(f"[bold red]Gagal membersihkan file: {e}[/bold red]"); return

    all_download_urls = []

    # 2. Proses Auto-discover dari apikeys.txt
    ui.console.print(f"[bold]Memulai Auto-Discover dari '{WEBSHARE_APIKEYS_FILE}'...[/bold]")
    api_keys = load_webshare_apikeys(WEBSHARE_APIKEYS_FILE)
    if not api_keys:
        ui.console.print(f"[yellow]'{WEBSHARE_APIKEYS_FILE}' kosong. Lanjut...[/yellow]")
    
    for api_key in api_keys:
        ui.console.print(f"\n--- Memproses API Key: [...{api_key[-6:]}] ---")
        with requests.Session() as session:
            session.headers.update({"Authorization": f"Token {api_key}", "Accept": "application/json"})
            try:
                plan_id = get_target_plan_id(session)
                if not plan_id:
                    ui.console.print("   -> [yellow]Gagal menemukan plan ID. Akun dilewati.[/yellow]")
                    continue
                
                download_url = get_webshare_download_url(session, plan_id)
                if download_url:
                    all_download_urls.append(download_url)
            except Exception as e:
                ui.console.print(f"   -> [bold red]!!! FATAL ERROR untuk akun ini: {e}[/bold red]")

    # 3. Proses URL manual dari apilist.txt
    ui.console.print(f"\n[bold]Memuat URL manual dari '{APILIST_SOURCE_FILE}'...[/bold]")
    manual_urls = load_apis(APILIST_SOURCE_FILE)
    if not manual_urls:
        ui.console.print(f"[yellow]'{APILIST_SOURCE_FILE}' kosong. Tidak ada URL manual.[/yellow]")
    else:
        ui.console.print(f"[green]Ditemukan {len(manual_urls)} URL manual.[/green]")
        all_download_urls.extend(manual_urls)

    # 4. Jalankan Proses Download
    if not all_download_urls:
        ui.console.print("\n[bold red]Tidak ada URL API (baik otomatis/manual) untuk diunduh.[/bold red]")
        return

    ui.console.print(f"\n[bold cyan]Siap mengunduh dari total {len(all_download_urls)} URL...[/bold cyan]")
    all_downloaded_proxies = ui.run_sequential_api_downloads(all_download_urls)

    if not all_downloaded_proxies:
        ui.console.print("\n[bold yellow]Tidak ada proksi yang berhasil diunduh dari semua API.[/bold yellow]")
        return

    # 5. Simpan ke proxylist.txt
    try:
        with open(PROXYLIST_SOURCE_FILE, "w") as f:
            for proxy in all_downloaded_proxies:
                f.write(proxy + "\n")
        
        ui.console.print(f"\n[bold green]✅ {len(all_downloaded_proxies)} proksi baru berhasil disimpan ke '{PROXYLIST_SOURCE_FILE}'[/bold green]")
    except IOError as e:
        ui.console.print(f"\n[bold red]Gagal menulis ke file '{PROXYLIST_SOURCE_FILE}': {e}[/bold red]")


# --- SISA FUNGSI (Konversi, Tes, Distribusi) ---

def convert_proxylist_to_http():
    if not os.path.exists(PROXYLIST_SOURCE_FILE):
        ui.console.print(f"[bold red]Error: '{PROXYLIST_SOURCE_FILE}' tidak ditemukan.[/bold red]")
        return

    try:
        with open(PROXYLIST_SOURCE_FILE, "r") as f:
            lines = f.readlines()
    except Exception as e:
        ui.console.print(f"[bold red]Gagal membaca file '{PROXYLIST_SOURCE_FILE}': {e}[/bold red]")
        return

    cleaned_proxies = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        parts = re.split(r'(https?://)', line)
        if len(parts) > 3:
            for i in range(1, len(parts), 2):
                cleaned_proxies.append(parts[i] + parts[i+1])
        else:
            cleaned_proxies.append(line)

    if not cleaned_proxies:
        ui.console.print(f"[yellow]'{PROXYLIST_SOURCE_FILE}' kosong.[/yellow]")
        return

    ui.console.print(f"Mengonversi {len(cleaned_proxies)} proksi...")
    
    converted_proxies = []
    for p in cleaned_proxies:
        if p.startswith("http://") or p.startswith("https://"):
            converted_proxies.append(p)
            continue
        parts = p.split(':')
        if len(parts) == 2:
            converted_proxies.append(f"http://{parts[0]}:{parts[1]}")
        elif len(parts) == 4:
            converted_proxies.append(f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}")
        elif len(parts) == 3 and '@' in parts[1]:
            converted_proxies.append(f"http://{p}")
        else:
            ui.console.print(f"[yellow]Format tidak dikenali: {p}[/yellow]")

    if not converted_proxies:
        ui.console.print("[bold red]Tidak ada proksi yang dikonversi.[/bold red]")
        return

    try:
        with open(PROXY_SOURCE_FILE, "w") as f:
            for proxy in converted_proxies:
                f.write(proxy + "\n")
        
        open(PROXYLIST_SOURCE_FILE, "w").close()
        
        ui.console.print(f"[bold green]✅ {len(converted_proxies)} proksi dipindahkan ke '{PROXY_SOURCE_FILE}'.[/bold green]")
        ui.console.print(f"[bold cyan]'{PROXYLIST_SOURCE_FILE}' telah dikosongkan.[/bold cyan]")

    except Exception as e:
        ui.console.print(f"[bold red]Gagal menulis ke file: {e}[/bold red]")


def load_and_deduplicate_proxies(file_path):
    if not os.path.exists(file_path): return []
    with open(file_path, "r") as f:
        proxies = [line.strip() for line in f if line.strip()]
    unique_proxies = sorted(list(set(proxies)))
    if len(proxies) > len(unique_proxies):
        ui.console.print(f"[yellow]Menghapus {len(proxies) - len(unique_proxies)} duplikat.[/yellow]")
    with open(file_path, "w") as f:
        for proxy in unique_proxies: f.write(proxy + "\n")
    return unique_proxies

def load_paths(file_path):
    if not os.path.exists(file_path): return []
    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip() and os.path.isdir(line.strip())]

def backup_file(file_path, backup_path):
    if os.path.exists(file_path):
        shutil.copy(file_path, backup_path)
        ui.console.print(f"[green]Backup dibuat: '{backup_path}'[/green]")

def check_proxy_final(proxy):
    """Fungsi pengetesan proksi yang telah dioptimalkan."""
    proxies_dict = {"http": proxy, "https": proxy}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    for url in CHECK_URLS: # Mencoba setiap URL di dalam daftar
        try:
            response = requests.get(url, proxies=proxies_dict, timeout=PROXY_TIMEOUT, headers=headers)
            
            if response.status_code == 407:
                return proxy, False, "Proxy Membutuhkan Otentikasi"
            
            response.raise_for_status() # Cek status 200 OK
            
            if '.' in response.text or ':' in response.text:
                return proxy, True, "OK"
            else:
                continue

        except requests.exceptions.RequestException:
            continue
            
    return proxy, False, "Gagal Terhubung"

def distribute_proxies(proxies, paths):
    if not proxies or not paths: return
    ui.console.print(f"\n[cyan]Mendistribusikan {len(proxies)} proksi valid...[/cyan]")
    for path in paths:
        if not os.path.isdir(path):
            ui.console.print(f"[yellow]Lewati path tidak valid: {path}[/yellow]")
            continue
        file_name = "proxies.txt" if os.path.exists(os.path.join(path, "proxies.txt")) else "proxy.txt"
        file_path = os.path.join(path, file_name)
        proxies_shuffled = random.sample(proxies, len(proxies))
        try:
            with open(file_path, "w") as f:
                for proxy in proxies_shuffled: f.write(proxy + "\n")
            ui.console.print(f"  [green]✔[/green] Berhasil menulis ke [bold]{file_path}[/bold]")
        except IOError as e:
            ui.console.print(f"  [red]✖[/red] Gagal menulis ke [bold]{file_path}[/bold]: {e}")

def save_good_proxies(proxies, file_path):
    try:
        with open(file_path, "w") as f:
            for proxy in proxies:
                f.write(proxy + "\n")
        ui.console.print(f"\n[bold green]✅ {len(proxies)} proksi valid berhasil disimpan ke '{file_path}'[/bold green]")
    except IOError as e:
        ui.console.print(f"\n[bold red]✖ Gagal menyimpan proksi: {e}[/bold red]")


def run_full_process():
    ui.print_header()
    distribute_choice = ui.Prompt.ask(
        "[bold yellow]Distribusikan proksi yang valid ke semua path target?[/bold yellow]",
        choices=["y", "n"], default="y"
    ).lower()
    
    ui.console.print("-" * 40)
    ui.console.print("[bold cyan]Langkah 1: Backup & Bersihkan Proksi...[/bold cyan]")
    backup_file(PROXY_SOURCE_FILE, PROXY_BACKUP_FILE)
    proxies = load_and_deduplicate_proxies(PROXY_SOURCE_FILE)
    if not proxies:
        ui.console.print("[bold red]Proses berhenti: 'proxy.txt' kosong.[/bold red]"); return
    ui.console.print(f"Siap menguji {len(proxies)} proksi unik.")
    ui.console.print("-" * 40)

    ui.console.print("[bold cyan]Langkah 2: Menjalankan Tes Akurat...[/bold cyan]")
    good_proxies = ui.run_concurrent_checks_display(proxies, check_proxy_final, MAX_WORKERS, FAIL_PROXY_FILE)
    if not good_proxies:
        ui.console.print("[bold red]Proses berhenti: Tidak ada proksi yang berfungsi.[/bold red]"); return
    ui.console.print(f"[bold green]Ditemukan {len(good_proxies)} proksi yang berfungsi.[/bold green]")
    ui.console.print("-" * 40)

    if distribute_choice == 'y':
        ui.console.print("[bold cyan]Langkah 3: Distribusi...[/bold cyan]")
        paths = load_paths(PATHS_SOURCE_FILE)
        if not paths:
            ui.console.print("[bold red]Proses berhenti: 'paths.txt' kosong.[/bold red]"); return
        distribute_proxies(good_proxies, paths)
        ui.console.print("\n[bold green]✅ Semua tugas selesai![/bold green]")
    else:
        ui.console.print(f"[bold cyan]Langkah 3: Menyimpan proksi valid...[/bold cyan]")
        save_good_proxies(good_proxies, SUCCESS_PROXY_FILE)


def main():
    while True:
        ui.print_header()
        choice = ui.display_main_menu()
        
        if choice == "1":
            run_webshare_ip_sync()
            ui.Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "2":
            # Fungsi ini sekarang sudah di-upgrade
            download_proxies_from_api() 
            ui.Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "3":
            convert_proxylist_to_http()
            ui.Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "4":
            run_full_process()
            ui.Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "5":
            ui.manage_paths_menu_display()
        elif choice == "6":
            ui.console.print("[bold cyan]Sampai jumpa![/bold cyan]"); break

if __name__ == "__main__":
    main()
