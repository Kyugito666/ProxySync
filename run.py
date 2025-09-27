import os
import random
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from rich.console import Console

# --- Konfigurasi ---
PROXYLIST_SOURCE_FILE = "proxylist.txt"
PROXY_SOURCE_FILE = "proxy.txt"
PATHS_SOURCE_FILE = "paths.txt"
FAIL_PROXY_FILE = "fail_proxy.txt"
PROXY_BACKUP_FILE = "proxy_backup.txt"
PROXY_TIMEOUT = 15
MAX_WORKERS = 25
CHECK_URLS = ["https://www.google.com", "https://api.ipify.org"]
RETRY_COUNT = 2 # Jumlah percobaan ulang jika proksi gagal

console = Console()

# --- FITUR BARU: Konversi Proksi ---
def convert_proxylist_to_http():
    """
    Membaca proksi dari proxylist.txt, mengubah formatnya,
    dan menyimpannya ke proxy.txt.
    """
    if not os.path.exists(PROXYLIST_SOURCE_FILE):
        console.print(f"[bold red]Error: File '{PROXYLIST_SOURCE_FILE}' tidak ditemukan.[/bold red]")
        return

    with open(PROXYLIST_SOURCE_FILE, "r") as f:
        raw_proxies = [line.strip() for line in f if line.strip()]

    if not raw_proxies:
        console.print(f"[yellow]'{PROXYLIST_SOURCE_FILE}' kosong, tidak ada yang perlu dikonversi.[/yellow]")
        return

    console.print(f"Menemukan {len(raw_proxies)} proksi di '{PROXYLIST_SOURCE_FILE}'. Mengonversi...")
    
    converted_proxies = []
    for line in raw_proxies:
        parts = line.split(':')
        if len(parts) == 4:
            ip, port, user, password = parts
            formatted_proxy = f"http://{user}:{password}@{ip}:{port}"
            converted_proxies.append(formatted_proxy)
        else:
            console.print(f"[yellow]Melewati baris dengan format salah: {line}[/yellow]")

    if not converted_proxies:
        console.print("[bold red]Tidak ada proksi yang berhasil dikonversi.[/bold red]")
        return

    # Menambahkan proksi yang sudah dikonversi ke proxy.txt dengan aman
    with open(PROXY_SOURCE_FILE, "a") as f:
        for proxy in converted_proxies:
            f.write(proxy + "\n")

    # Mengosongkan proxylist.txt setelah berhasil
    open(PROXYLIST_SOURCE_FILE, "w").close()

    console.print(f"[bold green]✅ Berhasil mengonversi dan memindahkan {len(converted_proxies)} proksi ke '{PROXY_SOURCE_FILE}'.[/bold green]")
    console.print(f"[cyan]'{PROXYLIST_SOURCE_FILE}' sekarang kosong.[/cyan]")


# --- Logika Inti (dari skrip asli yang sudah stabil) ---
def load_and_deduplicate_proxies(file_path):
    if not os.path.exists(file_path): return []
    with open(file_path, "r") as f:
        proxies = [line.strip() for line in f if line.strip()]
    unique_proxies = sorted(list(set(proxies)))
    if len(proxies) > len(unique_proxies):
        console.print(f"[yellow]Menghapus {len(proxies) - len(unique_proxies)} proksi duplikat.[/yellow]")
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
        console.print(f"[green]Backup dibuat: '{file_path}' -> '{backup_path}'[/green]")

# --- FITUR BARU: Pengecekan Ulang yang Lebih Ketat ---
def check_proxy_with_retry(proxy):
    """
    Mengecek satu proksi. Jika gagal, coba lagi sekali untuk memastikan.
    """
    proxies_dict = {"http": proxy, "https": proxy}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    for attempt in range(RETRY_COUNT):
        try:
            # Pengecekan harus lolos semua URL
            for url in CHECK_URLS:
                response = requests.get(url, proxies=proxies_dict, timeout=PROXY_TIMEOUT, headers=headers)
                response.raise_for_status()
            # Jika semua URL lolos, proksi dianggap bagus
            return proxy, True, "OK"
        except requests.exceptions.RequestException:
            if attempt < RETRY_COUNT - 1:
                time.sleep(1) # Tunggu 1 detik sebelum mencoba lagi
            else:
                # Jika sudah percobaan terakhir dan masih gagal
                return proxy, False, "Gagal setelah beberapa percobaan"

    return proxy, False, "Gagal" # Seharusnya tidak pernah sampai sini


def distribute_proxies(proxies, paths):
    if not proxies or not paths:
        console.print("[red]Tidak ada proksi valid atau path untuk didistribusikan.[/red]")
        return
    console.print(f"\n[cyan]Mendistribusikan {len(proxies)} proksi valid ke {len(paths)} direktori...[/cyan]")
    for path in paths:
        if not os.path.isdir(path):
            console.print(f"[yellow]Peringatan: Path tidak ditemukan, dilewati: {path}[/yellow]")
            continue
        
        file_name = "proxy.txt"
        if os.path.exists(os.path.join(path, "proxies.txt")):
            file_name = "proxies.txt"
        
        file_path = os.path.join(path, file_name)
        
        proxies_shuffled = random.sample(proxies, len(proxies))

        try:
            with open(file_path, "w") as f:
                for proxy in proxies_shuffled:
                    f.write(proxy + "\n")
            console.print(f"  [green]✔[/green] Berhasil menulis ke [bold]{file_path}[/bold]")
        except IOError as e:
            console.print(f"  [red]✖[/red] Gagal menulis ke [bold]{file_path}[/bold]: {e}")
