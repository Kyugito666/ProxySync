import os
import random
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (BarColumn, Progress, SpinnerColumn, TextColumn,
                           TimeRemainingColumn)
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

# --- Konfigurasi ---
PROXY_SOURCE_FILE = "proxy.txt"
PATHS_SOURCE_FILE = "paths.txt"
FAIL_PROXY_FILE = "fail_proxy.txt"
PROXY_BACKUP_FILE = "proxy_backup.txt"
PROXY_TIMEOUT = 10
MAX_WORKERS = 30
CHECK_URLS = [
    "http://www.google.com",
    "http://ifconfig.me/ip",
    "https://api.ipify.org"
]

# --- Inisialisasi UI ---
console = Console()

def print_header():
    """Menampilkan header aplikasi."""
    console.clear()
    title = Text("ProxySync Universal (HTTP/SOCKS5)", style="bold #5f9ea0", justify="center")
    credits = Text("Created by Kyugito666 & Gemini AI", style="bold magenta", justify="center")
    header_table = Table.grid(expand=True)
    header_table.add_row(title)
    header_table.add_row(credits)
    console.print(Panel(header_table, border_style="#5f9ea0"))
    console.print()

# --- Logika Inti ---
def reformat_proxy(line):
    """
    Mendeteksi format proksi (HTTP/SOCKS5) dan mengubahnya ke format URL.
    Format yang didukung:
    - ip:port:user:pass -> http://user:pass@ip:port
    - socks5:ip:port:user:pass -> socks5://user:pass@ip:port
    """
    line = line.strip()
    if not line:
        return None
        
    parts = line.split(':')
    
    # Format SOCKS5: socks5:ip:port:user:pass (5 bagian)
    if len(parts) == 5 and parts[0].lower() in ['socks5', 'socks4']:
        proto, ip, port, user, password = parts
        return f"{proto.lower()}://{user}:{password}@{ip}:{port}"
        
    # Format HTTP: ip:port:user:pass (4 bagian)
    elif len(parts) == 4:
        ip, port, user, password = parts
        return f"http://{user}:{password}@{ip}:{port}"
        
    # Asumsikan format sudah benar jika bukan format di atas
    elif '://' in line:
        return line
        
    console.print(f"[yellow]Peringatan: Format tidak dikenali, dilewati: {line}[/yellow]")
    return None

def load_and_process_proxies(file_path):
    """Memuat proksi, memformat ulang secara otomatis, dan menghapus duplikat."""
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error: '{file_path}' tidak ditemukan.[/bold red]")
        return []
    
    formatted_proxies = []
    with open(file_path, "r") as f:
        for line in f:
            formatted_proxy = reformat_proxy(line)
            if formatted_proxy:
                formatted_proxies.append(formatted_proxy)

    if not formatted_proxies:
        console.print(f"[yellow]'{file_path}' kosong atau tidak ada proksi dengan format yang benar.[/yellow]")
        return []

    unique_proxies = sorted(list(set(formatted_proxies)))
    num_duplicates = len(formatted_proxies) - len(unique_proxies)

    if num_duplicates > 0:
        console.print(f"[yellow]Menghapus {num_duplicates} proksi duplikat.[/yellow]")
    
    with open(file_path, "w") as f:
        for proxy in unique_proxies:
            f.write(proxy + "\n")
    
    console.print(f"[green]Berhasil memuat dan memproses {len(unique_proxies)} proksi unik.[/green]")
    return unique_proxies

def check_proxy_universal(proxy):
    """Mengecek proksi (HTTP atau SOCKS) dengan metode ketat."""
    proxies_dict = {
        "http": proxy,
        "https": proxy
    }
    
    for url in CHECK_URLS:
        try:
            # Pengecekan dilakukan menggunakan dictionary yang sama untuk HTTP dan SOCKS
            # Library requests dengan pysocks akan menanganinya secara otomatis
            response = requests.get(url, proxies=proxies_dict, timeout=PROXY_TIMEOUT)
            if response.status_code != 200:
                return proxy, False, f"Gagal di {url} (Status: {response.status_code})"
        except requests.exceptions.RequestException as e:
            error_type = type(e).__name__
            return proxy, False, f"Gagal di {url} ({error_type})"
    
    return proxy, True, "OK (Semua target lolos)"

def run_concurrent_checks(proxies):
    """Menjalankan pengecekan proksi secara konkuren."""
    good_proxies = []
    failed_proxies = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"), BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), TimeRemainingColumn(),
        console=console
    )

    with Live(progress):
        task = progress.add_task("[cyan]Mengecek proksi (Mode Universal)...[/cyan]", total=len(proxies))
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_proxy = {executor.submit(check_proxy_universal, p): p for p in proxies}
            for future in as_completed(future_to_proxy):
                proxy, is_good, message = future.result()
                (good_proxies if is_good else failed_proxies).append(proxy)
                progress.update(task, advance=1)

    if failed_proxies:
        with open(FAIL_PROXY_FILE, "w") as f:
            for p in failed_proxies: f.write(p + "\n")
        console.print(f"[yellow]Menyimpan {len(failed_proxies)} proksi gagal ke '{FAIL_PROXY_FILE}'[/yellow]")
    
    return good_proxies

def distribute_proxies(proxies, paths):
    """Mendistribusikan proksi yang valid ke setiap direktori target."""
    # ... (Fungsi ini tidak perlu diubah)
    if not proxies or not paths:
        console.print("[red]Tidak ada proksi valid atau path untuk didistribusikan.[/red]")
        return

    console.print("\n[cyan]Mendistribusikan proksi valid ke direktori target...[/cyan]")
    for path in paths:
        if not os.path.isdir(path):
            console.print(f"[yellow]Peringatan: Path tidak ditemukan, dilewati: {path}[/yellow]")
            continue

        target_file_name = "proxy.txt"
        if os.path.exists(os.path.join(path, "proxies.txt")):
            target_file_name = "proxies.txt"

        file_path = os.path.join(path, target_file_name)
        proxies_shuffled = random.sample(proxies, len(proxies))

        try:
            with open(file_path, "w") as f:
                for proxy in proxies_shuffled:
                    f.write(proxy + "\n")
            console.print(f"  [green]✔[/green] Berhasil menulis ke [bold]{file_path}[/bold]")
        except IOError as e:
            console.print(f"  [red]✖[/red] Gagal menulis ke [bold]{file_path}[/bold]: {e}")
            
# --- Fungsi Menu dan UI ---
def manage_paths_menu():
    # ... (Fungsi ini tidak perlu diubah)
    load_paths = lambda file_path: [line.strip() for line in open(file_path)] if os.path.exists(file_path) else []
    while True:
        print_header()
        paths = load_paths(PATHS_SOURCE_FILE)
        table = Table(title=f"Path Target ({len(paths)} ditemukan)", border_style="yellow")
        table.add_column("#", style="dim", width=4)
        table.add_column("Directory Path")
        for i, path in enumerate(paths):
            status = "✔ Ditemukan" if os.path.exists(path) else "✖ Tidak Ditemukan"
            color = "green" if os.path.exists(path) else "red"
            table.add_row(str(i + 1), f"[{color}]{path} ({status})[/{color}]")
        console.print(table)
        console.print("\n[cyan][A][/cyan]dd | [cyan][D][/cyan]elete | [cyan][B][/cyan]ack")
        choice = Prompt.ask("Pilih opsi", choices=["A", "D", "B"], default="B").upper()
        if choice == "A":
            new_path = Prompt.ask("Masukkan path lengkap").strip()
            if os.path.isdir(new_path):
                with open(PATHS_SOURCE_FILE, "a") as f: f.write(f"\n{new_path}")
                console.print(f"[green]Path '{new_path}' ditambahkan.[/green]")
            else:
                console.print(f"[red]Error: '{new_path}' bukan direktori valid.[/red]")
            time.sleep(1.5)
        elif choice == "D":
            if not paths: console.print("[yellow]Tidak ada path untuk dihapus.[/yellow]"); time.sleep(1.5); continue
            try:
                num_to_delete = int(Prompt.ask("Masukkan nomor # path yang akan dihapus"))
                if 1 <= num_to_delete <= len(paths):
                    deleted_path = paths.pop(num_to_delete - 1)
                    with open(PATHS_SOURCE_FILE, "w") as f:
                        for p in paths: f.write(p + "\n")
                    console.print(f"[green]Path '{deleted_path}' dihapus.[/green]")
                else: console.print("[red]Nomor tidak valid.[/red]")
            except ValueError: console.print("[red]Silakan masukkan nomor yang valid.[/red]")
            time.sleep(1.5)
        elif choice == "B": break

def display_main_menu():
    """Menampilkan menu utama."""
    menu_table = Table(title="Main Menu", show_header=False, border_style="magenta")
    menu_table.add_column("Option", style="cyan", width=5)
    menu_table.add_column("Description")
    menu_table.add_row("[1]", "Jalankan Proses Penuh (Mode Universal)")
    menu_table.add_row("[2]", "Kelola Path Target")
    menu_table.add_row("[3]", "Keluar")
    console.print(Align.center(menu_table))

def run_full_process():
    """Menjalankan seluruh alur kerja pemrosesan proksi."""
    print_header()
    # Langkah 1
    console.print("[bold cyan]Langkah 1: Mem-backup file proksi...[/bold cyan]")
    if os.path.exists(PROXY_SOURCE_FILE): shutil.copy(PROXY_SOURCE_FILE, PROXY_BACKUP_FILE); console.print(f"[green]Backup dibuat: '{PROXY_BACKUP_FILE}'[/green]")
    console.print("-" * 40)
    # Langkah 2
    console.print("[bold cyan]Langkah 2: Memuat, memformat, dan membersihkan proksi...[/bold cyan]")
    proxies = load_and_process_proxies(PROXY_SOURCE_FILE)
    if not proxies: console.print("[bold red]Proses dihentikan: Tidak ada proksi untuk dicek.[/bold red]"); return
    console.print("-" * 40)
    # Langkah 3
    console.print("[bold cyan]Langkah 3: Mengecek proksi yang aktif (Mode Universal)...[/bold cyan]")
    good_proxies = run_concurrent_checks(proxies)
    if not good_proxies: console.print("[bold red]Proses dihentikan: Tidak ada proksi yang berfungsi ditemukan.[/bold red]"); return
    console.print(f"[bold green]Ditemukan {len(good_proxies)} proksi yang berfungsi.[/bold green]")
    console.print("-" * 40)
    # Langkah 4
    console.print("[bold cyan]Langkah 4: Memuat path target...[/bold cyan]")
    paths = [line.strip() for line in open(PATHS_SOURCE_FILE)] if os.path.exists(PATHS_SOURCE_FILE) else []
    if not paths: console.print("[bold red]Proses dihentikan: Tidak ada path valid di 'paths.txt'.[/bold red]"); return
    console.print(f"Ditemukan {len(paths)} direktori target yang valid.")
    console.print("-" * 40)
    # Langkah 5
    distribute_proxies(good_proxies, paths)
    console.print("\n[bold green]✅ Semua tugas selesai dengan sukses![/bold green]")

# --- Loop Aplikasi Utama ---
def main():
    while True:
        print_header()
        display_main_menu()
        choice = Prompt.ask("Pilih opsi", choices=["1", "2", "3"], default="3")
        if choice == "1":
            run_full_process()
            Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "2":
            manage_paths_menu()
        elif choice == "3":
            console.print("[bold cyan]Sampai jumpa![/bold cyan]")
            break

if __name__ == "__main__":
    main()
