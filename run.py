import os
import random
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
import requests
import ui  # Mengimpor semua fungsi UI dari file ui.py

# --- Konfigurasi ---
PROXYLIST_SOURCE_FILE = "proxylist.txt"
PROXY_SOURCE_FILE = "proxy.txt"
PATHS_SOURCE_FILE = "paths.txt"
FAIL_PROXY_FILE = "fail_proxy.txt"
PROXY_BACKUP_FILE = "proxy_backup.txt"
PROXY_TIMEOUT = 10
MAX_WORKERS = 30
# --- PERUBAHAN DI SINI: Target tes diubah ke situs yang lebih ramah proksi ---
CHECK_URL = "https://api.ipify.org"
RETRY_COUNT = 2

# --- FUNGSI LOGIKA INTI ---
def convert_proxylist_to_http():
    """
    Mengonversi berbagai format proxy dari proxylist.txt ke format HTTP standar
    dan menyimpannya di proxy.txt.
    Mendukung format:
    - ip:port
    - ip:port:user:pass
    - user:pass@ip:port
    - http://user:pass@ip:port (sudah benar, akan disalin saja)
    """
    if not os.path.exists(PROXYLIST_SOURCE_FILE):
        ui.console.print(f"[bold red]Error: '{PROXYLIST_SOURCE_FILE}' tidak ditemukan.[/bold red]")
        return

    try:
        with open(PROXYLIST_SOURCE_FILE, "r") as f:
            raw_proxies = [line.strip() for line in f if line.strip()]
    except Exception as e:
        ui.console.print(f"[bold red]Gagal membaca file '{PROXYLIST_SOURCE_FILE}': {e}[/bold red]")
        return
        
    if not raw_proxies:
        ui.console.print(f"[yellow]'{PROXYLIST_SOURCE_FILE}' kosong atau tidak berisi proksi yang valid.[/yellow]")
        return

    ui.console.print(f"Mendeteksi dan mengonversi {len(raw_proxies)} proksi...")
    
    converted_proxies = []
    for line in raw_proxies:
        # Jika sudah dalam format URL, langsung tambahkan
        if line.startswith("http://") or line.startswith("https://"):
            converted_proxies.append(line)
            continue
            
        parts = line.split(':')
        
        # Kasus 1: ip:port
        if len(parts) == 2:
            ip, port = parts
            converted_proxies.append(f"http://{ip}:{port}")
            
        # Kasus 2: ip:port:user:pass
        elif len(parts) == 4:
            # Periksa apakah ada '@' untuk membedakan user:pass@ip:port
            if '@' in parts[1]: # Kemungkinan formatnya user:pass@ip:port
                 # Coba gabungkan kembali dan proses
                 at_parts = line.split('@')
                 if len(at_parts) == 2:
                     converted_proxies.append(f"http://{line}")
            else: # Asumsi ip:port:user:pass
                ip, port, user, password = parts
                converted_proxies.append(f"http://{user}:{password}@{ip}:{port}")
        
        # Kasus 3: user:pass@ip:port (di-split oleh :)
        elif len(parts) == 3 and '@' in parts[1]:
             converted_proxies.append(f"http://{line}")

        else:
            ui.console.print(f"[yellow]Format tidak dikenali dan dilewati: {line}[/yellow]")


    if not converted_proxies:
        ui.console.print("[bold red]Tidak ada proksi yang berhasil dikonversi.[/bold red]")
        return

    try:
        # Menggunakan mode 'a' (append) untuk menambahkan ke proxy.txt yang sudah ada
        with open(PROXY_SOURCE_FILE, "a") as f:
            for proxy in converted_proxies:
                f.write(proxy + "\n")
        
        # Mengosongkan proxylist.txt setelah berhasil diproses
        open(PROXYLIST_SOURCE_FILE, "w").close()
        
        ui.console.print(f"[bold green]✅ {len(converted_proxies)} proksi berhasil dikonversi dan ditambahkan ke '{PROXY_SOURCE_FILE}'.[/bold green]")
        ui.console.print(f"[bold cyan]'{PROXYLIST_SOURCE_FILE}' telah dikosongkan.[/bold cyan]")

    except Exception as e:
        ui.console.print(f"[bold red]Gagal menulis ke file '{PROXY_SOURCE_FILE}': {e}[/bold red]")


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
                return proxy, False, "Proxy Authentication Required (Cek Otorisasi IP)"
            response.raise_for_status()
            # Memastikan respons berisi alamat IP yang valid
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

def run_full_process():
    ui.print_header()
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

    ui.console.print("[bold cyan]Langkah 3: Distribusi...[/bold cyan]")
    paths = load_paths(PATHS_SOURCE_FILE)
    if not paths:
        ui.console.print("[bold red]Proses berhenti: 'paths.txt' kosong.[/bold red]"); return
    distribute_proxies(good_proxies, paths)
    ui.console.print("\n[bold green]✅ Semua tugas selesai![/bold green]")

def main():
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
            ui.console.print("[bold cyan]Sampai jumpa![/bold cyan]"); break

if __name__ == "__main__":
    main()
