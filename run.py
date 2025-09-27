import os
import random
import shutil
import time
from concurrent.futures import ThreadPoolExecutor

import requests
# Mengimpor semua fungsi UI dari file ui.py
import ui

# --- Konfigurasi ---
PROXYLIST_SOURCE_FILE = "proxylist.txt"
PROXY_SOURCE_FILE = "proxy.txt"
PATHS_SOURCE_FILE = "paths.txt"
FAIL_PROXY_FILE = "fail_proxy.txt"
PROXY_BACKUP_FILE = "proxy_backup.txt"
PROXY_TIMEOUT = 15
MAX_WORKERS = 25
CHECK_URLS = ["https://www.google.com", "https://api.ipify.org"]
RETRY_COUNT = 2

# --- FUNGSI LOGIKA INTI ---

def convert_proxylist_to_http():
    """Membaca dari proxylist.txt, konversi, dan simpan ke proxy.txt."""
    if not os.path.exists(PROXYLIST_SOURCE_FILE):
        ui.console.print(f"[bold red]Error: '{PROXYLIST_SOURCE_FILE}' tidak ditemukan.[/bold red]")
        return
    with open(PROXYLIST_SOURCE_FILE, "r") as f:
        raw_proxies = [line.strip() for line in f if line.strip()]
    if not raw_proxies:
        ui.console.print(f"[yellow]'{PROXYLIST_SOURCE_FILE}' kosong.[/yellow]")
        return

    ui.console.print(f"Mengonversi {len(raw_proxies)} proksi...")
    converted_proxies = []
    for line in raw_proxies:
        parts = line.split(':')
        if len(parts) == 4:
            ip, port, user, password = parts
            converted_proxies.append(f"http://{user}:{password}@{ip}:{port}")
    
    with open(PROXY_SOURCE_FILE, "a") as f:
        for proxy in converted_proxies: f.write(proxy + "\n")
    
    open(PROXYLIST_SOURCE_FILE, "w").close()
    ui.console.print(f"[bold green]✅ {len(converted_proxies)} proksi dipindahkan ke '{PROXY_SOURCE_FILE}'.[/bold green]")

def load_and_deduplicate_proxies(file_path):
    """Memuat dan membersihkan duplikat dari proxy.txt."""
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
    """Memuat semua path tujuan."""
    if not os.path.exists(file_path): return []
    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip() and os.path.isdir(line.strip())]

def backup_file(file_path, backup_path):
    """Membuat backup file proxy."""
    if os.path.exists(file_path):
        shutil.copy(file_path, backup_path)
        ui.console.print(f"[green]Backup dibuat: '{backup_path}'[/green]")

def check_proxy_with_retry(proxy):
    """Mengecek proksi dengan mekanisme coba lagi."""
    proxies_dict = {"http": proxy, "https": proxy}
    headers = {'User-Agent': 'Mozilla/5.0'}
    for attempt in range(RETRY_COUNT):
        try:
            for url in CHECK_URLS:
                response = requests.get(url, proxies=proxies_dict, timeout=PROXY_TIMEOUT, headers=headers)
                response.raise_for_status()
            return proxy, True, "OK"
        except requests.exceptions.RequestException:
            if attempt < RETRY_COUNT - 1:
                time.sleep(1)
            else:
                return proxy, False, "Gagal"
    return proxy, False, "Gagal"

def distribute_proxies(proxies, paths):
    """Mendistribusikan proksi yang valid ke semua path."""
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

def run_full_process():
    """Alur kerja utama untuk mengecek dan distribusi."""
    ui.print_header()
    ui.console.print("[bold cyan]Langkah 1: Backup & Bersihkan Proksi...[/bold cyan]")
    backup_file(PROXY_SOURCE_FILE, PROXY_BACKUP_FILE)
    proxies = load_and_deduplicate_proxies(PROXY_SOURCE_FILE)
    if not proxies:
        ui.console.print("[bold red]Proses berhenti: 'proxy.txt' kosong.[/bold red]")
        return
    ui.console.print(f"Siap menguji {len(proxies)} proksi unik.")
    ui.console.print("-" * 40)

    ui.console.print("[bold cyan]Langkah 2: Mengecek Proksi...[/bold cyan]")
    good_proxies = ui.run_concurrent_checks_display(proxies, check_proxy_with_retry, MAX_WORKERS, FAIL_PROXY_FILE)
    if not good_proxies:
        ui.console.print("[bold red]Proses berhenti: Tidak ada proksi yang berfungsi.[/bold red]")
        return
    ui.console.print(f"[bold green]Ditemukan {len(good_proxies)} proksi yang berfungsi.[/bold green]")
    ui.console.print("-" * 40)

    ui.console.print("[bold cyan]Langkah 3: Distribusi...[/bold cyan]")
    paths = load_paths(PATHS_SOURCE_FILE)
    if not paths:
        ui.console.print("[bold red]Proses berhenti: 'paths.txt' kosong.[/bold red]")
        return
    distribute_proxies(good_proxies, paths)
    ui.console.print("\n[bold green]✅ Semua tugas selesai![/bold green]")

# --- TITIK MASUK UTAMA APLIKASI ---
def main():
    """Fungsi utama untuk menjalankan aplikasi."""
    while True:
        ui.print_header()
        choice = ui.display_main_menu()

        if choice == "1":
            convert_proxylist_to_http()
            ui.Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "2":
            run_full_process()
            ui.Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "3":
            ui.manage_paths_menu_display()
        elif choice == "4":
            ui.console.print("[bold cyan]Sampai jumpa![/bold cyan]")
            break

if __name__ == "__main__":
    main()
