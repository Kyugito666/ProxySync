import os
import random
import shutil
import time
import re
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
PROXY_TIMEOUT = 10
MAX_WORKERS = 50
API_DOWNLOAD_WORKERS = 3 # Kecepatan optimal yang tidak terlalu agresif
CHECK_URL = "https://api.ipify.org"
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

def download_proxies_from_api():
    """Mengosongkan proxylist.txt lalu mengunduh proksi dari semua API dengan auto-retry cerdas."""
    
    if os.path.exists(PROXYLIST_SOURCE_FILE) and os.path.getsize(PROXYLIST_SOURCE_FILE) > 0:
        choice = ui.Prompt.ask(
            f"[bold yellow]File '{PROXYLIST_SOURCE_FILE}' berisi data. Hapus konten lama sebelum mengunduh?[/bold yellow]",
            choices=["y", "n"],
            default="y"
        ).lower()
        if choice == 'n':
            ui.console.print("[cyan]Operasi dibatalkan. Proksi tidak diunduh.[/cyan]")
            return
    
    try:
        with open(PROXYLIST_SOURCE_FILE, "w") as f:
            pass
        ui.console.print(f"[green]'{PROXYLIST_SOURCE_FILE}' telah siap untuk diisi data baru.[/green]\n")
    except IOError as e:
        ui.console.print(f"[bold red]Gagal membersihkan file: {e}[/bold red]")
        return

    api_urls = load_apis(APILIST_SOURCE_FILE)
    if not api_urls:
        ui.console.print(f"[bold red]File '{APILIST_SOURCE_FILE}' kosong atau tidak ditemukan.[/bold red]")
        ui.console.print(f"[yellow]Silakan isi file tersebut dengan URL API Anda.[/yellow]")
        return

    all_downloaded_proxies = ui.run_concurrent_api_downloads(api_urls, API_DOWNLOAD_WORKERS)

    if not all_downloaded_proxies:
        ui.console.print("\n[bold yellow]Tidak ada proksi yang berhasil diunduh dari semua API.[/bold yellow]")
        return

    try:
        with open(PROXYLIST_SOURCE_FILE, "w") as f:
            for proxy in all_downloaded_proxies:
                f.write(proxy + "\n")
        
        ui.console.print(f"\n[bold green]✅ {len(all_downloaded_proxies)} proksi baru berhasil disimpan ke '{PROXYLIST_SOURCE_FILE}'[/bold green]")
    except IOError as e:
        ui.console.print(f"\n[bold red]Gagal menulis ke file '{PROXYLIST_SOURCE_FILE}': {e}[/bold red]")


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
    proxies_dict = {"http": proxy, "https": proxy}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
    for attempt in range(RETRY_COUNT):
        try:
            response = requests.get(CHECK_URL, proxies=proxies_dict, timeout=PROXY_TIMEOUT, headers=headers)
            if response.status_code == 407:
                return proxy, False, "Proxy Authentication Required"
            response.raise_for_status()
            if '.' in response.text or ':' in response.text:
                return proxy, True, "OK"
            else:
                return proxy, False, "Respons tidak valid"
        except requests.exceptions.RequestException:
            if attempt < RETRY_COUNT - 1:
                time.sleep(1)
            else:
                return proxy, False, "Gagal Terhubung"
    return proxy, False, "Gagal"

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
            download_proxies_from_api()
            ui.Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "2":
            convert_proxylist_to_http()
            ui.Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "3":
            run_full_process()
            ui.Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "4":
            ui.manage_paths_menu_display()
        elif choice == "5":
            ui.console.print("[bold cyan]Sampai jumpa![/bold cyan]"); break

if __name__ == "__main__":
    main()
