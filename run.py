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
MAX_WORKERS = 25  # Bisa dinaikkan jika koneksi internet kuat
# URL target untuk validasi. Proksi HARUS berhasil terhubung ke SEMUA URL ini.
CHECK_URLS = [
    "http://www.google.com",
    "http://ifconfig.me/ip",
    "http://www.bing.com",
    "https://api.ipify.org"
]

# --- Inisialisasi UI dan Konsol ---
console = Console()

def print_header():
    """Menampilkan header aplikasi."""
    console.clear()
    title = Text("ProxySync Pro (Strict Mode)", style="bold yellow", justify="center")
    credits = Text("Created by Kyugito666 & Gemini AI", style="bold magenta", justify="center")
    header_table = Table.grid(expand=True)
    header_table.add_row(title)
    header_table.add_row(credits)
    console.print(Panel(header_table, border_style="yellow"))
    console.print()

# --- Logika Inti ---
def load_and_deduplicate_proxies(file_path):
    """Memuat proksi dari file dan menghapus duplikat."""
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error: '{file_path}' tidak ditemukan.[/bold red]")
        return []
    with open(file_path, "r") as f:
        proxies = [line.strip() for line in f if line.strip()]
    if not proxies:
        console.print(f"[yellow]'{file_path}' kosong.[/yellow]")
        return []
    unique_proxies = sorted(list(set(proxies)))
    num_duplicates = len(proxies) - len(unique_proxies)
    if num_duplicates > 0:
        console.print(f"[yellow]Menghapus {num_duplicates} proksi duplikat.[/yellow]")
    with open(file_path, "w") as f:
        for proxy in unique_proxies:
            f.write(proxy + "\n")
    return unique_proxies

def load_paths(file_path):
    """Memuat path target dari file."""
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error: File path '{file_path}' tidak ditemukan.[/bold red]")
        return []
    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip() and os.path.isdir(line.strip())]

def backup_file(file_path, backup_path):
    """Membuat backup dari file yang diberikan."""
    if os.path.exists(file_path):
        shutil.copy(file_path, backup_path)
        console.print(f"[green]Backup dibuat: '{file_path}' -> '{backup_path}'[/green]")

def format_proxy(proxy):
    """Memastikan URL proksi diformat dengan benar."""
    if not (proxy.startswith("http://") or proxy.startswith("https://")):
        return f"http://{proxy}"
    return proxy

def check_proxy_strict(proxy):
    """
    Mengecek satu proksi dengan metode KETAT.
    Proksi dianggap valid HANYA JIKA berhasil terhubung ke SEMUA URL target.
    """
    proxy_url = format_proxy(proxy)
    proxies_dict = {"http": proxy_url, "https": proxy_url}

    for url in CHECK_URLS:
        try:
            response = requests.get(url, proxies=proxies_dict, timeout=PROXY_TIMEOUT)
            if response.status_code != 200:
                # Jika salah satu URL gagal, langsung gagalkan seluruh proksi
                return proxy, False, f"Failed at {url} (Status: {response.status_code})"
        except requests.exceptions.RequestException as e:
            # Jika ada error koneksi, langsung gagalkan
            error_type = type(e).__name__
            return proxy, False, f"Failed at {url} ({error_type})"
    
    # Jika loop selesai tanpa gagal, berarti semua URL berhasil
    return proxy, True, "OK (All targets passed)"


def check_proxies_concurrently(proxies):
    """Mengecek daftar proksi menggunakan multi-thread dan menampilkan progres."""
    good_proxies = []
    failed_proxies = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    )

    with Live(progress):
        task = progress.add_task("[cyan]Mengecek proksi (Mode Ketat)...[/cyan]", total=len(proxies))
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_proxy = {executor.submit(check_proxy_strict, p): p for p in proxies}
            for future in as_completed(future_to_proxy):
                proxy, is_good, message = future.result()
                if is_good:
                    good_proxies.append(proxy)
                else:
                    failed_proxies.append(proxy)
                progress.update(task, advance=1)

    if failed_proxies:
        with open(FAIL_PROXY_FILE, "w") as f:
            for p in failed_proxies:
                f.write(p + "\n")
        console.print(f"[yellow]Menyimpan {len(failed_proxies)} proksi gagal ke '{FAIL_PROXY_FILE}'[/yellow]")

    return good_proxies

def distribute_proxies(proxies, paths):
    """Menyimpan daftar proksi yang sudah diacak ke setiap path target."""
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

# --- Fungsi Menu dan UI (Tidak ada perubahan signifikan di sini) ---
def display_main_menu():
    menu_table = Table(title="Main Menu", show_header=False, border_style="magenta")
    menu_table.add_column("Option", style="cyan", width=5)
    menu_table.add_column("Description")
    menu_table.add_row("[1]", "Jalankan Proses Penuh (Mode Ketat)")
    menu_table.add_row("[2]", "Kelola Path Target")
    menu_table.add_row("[3]", "Keluar")
    console.print(Align.center(menu_table))

def manage_paths_menu():
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
            if not paths:
                console.print("[yellow]Tidak ada path untuk dihapus.[/yellow]")
                time.sleep(1.5)
                continue
            try:
                num_to_delete = int(Prompt.ask("Masukkan nomor # path yang akan dihapus"))
                if 1 <= num_to_delete <= len(paths):
                    deleted_path = paths.pop(num_to_delete - 1)
                    with open(PATHS_SOURCE_FILE, "w") as f:
                        for p in paths: f.write(p + "\n")
                    console.print(f"[green]Path '{deleted_path}' dihapus.[/green]")
                else:
                    console.print("[red]Nomor tidak valid.[/red]")
            except ValueError:
                console.print("[red]Silakan masukkan nomor yang valid.[/red]")
            time.sleep(1.5)
        elif choice == "B":
            break

def run_full_process():
    print_header()
    console.print("[bold yellow]Langkah 1: Mem-backup file proksi...[/bold yellow]")
    backup_file(PROXY_SOURCE_FILE, PROXY_BACKUP_FILE)
    console.print("-" * 30)
    console.print("[bold yellow]Langkah 2: Memuat dan membersihkan daftar proksi...[/bold yellow]")
    proxies = load_and_deduplicate_proxies(PROXY_SOURCE_FILE)
    if not proxies:
        console.print("[bold red]Proses dihentikan: Tidak ada proksi untuk dicek.[/bold red]")
        return
    console.print(f"Ditemukan {len(proxies)} proksi unik untuk dites.")
    console.print("-" * 30)
    console.print("[bold yellow]Langkah 3: Mengecek proksi yang aktif (Mode Ketat)...[/bold yellow]")
    good_proxies = check_proxies_concurrently(proxies)
    if not good_proxies:
        console.print("[bold red]Proses dihentikan: Tidak ada proksi yang berfungsi ditemukan.[/bold red]")
        return
    console.print(f"[bold green]Ditemukan {len(good_proxies)} proksi yang berfungsi.[/bold green]")
    console.print("-" * 30)
    console.print("[bold yellow]Langkah 4: Memuat path target...[/bold yellow]")
    paths = load_paths(PATHS_SOURCE_FILE)
    if not paths:
        console.print("[bold red]Proses dihentikan: Tidak ada path valid di 'paths.txt'.[/bold red]")
        return
    console.print(f"Ditemukan {len(paths)} direktori target yang valid.")
    console.print("-" * 30)
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
