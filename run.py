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
PROXY_TIMEOUT = 20
MAX_WORKERS = 30
CHECK_URLS = ["https://www.google.com", "https://ifconfig.me/ip"]

# --- Inisialisasi UI ---
console = Console()

def print_header():
    console.clear()
    title = Text("ProxySync Auto-Repair Mode", style="bold bright_green", justify="center")
    credits = Text("Created by Kyugito666 & Gemini AI", style="bold magenta", justify="center")
    header_table = Table.grid(expand=True)
    header_table.add_row(title)
    header_table.add_row(credits)
    console.print(Panel(header_table, border_style="bright_green"))
    console.print()

# --- BAGIAN PALING PENTING: FUNGSI REPARASI BARU ---
def repair_and_reformat_proxy(line):
    """
    Fungsi cerdas untuk memperbaiki format proksi yang rusak dan menstandarkannya.
    """
    line = line.strip()
    try:
        # Pola 1: Format rusak dari file Anda (http:////pass@ip@http://port...)
        if line.count('@') > 2 and line.startswith("http:////"):
            parts = line.split('@')
            password = parts[1]
            ip = parts[2]
            port = parts[3].replace('http://', '')
            username = parts[-1].replace('//', '').replace('http', '')
            return f"http://{username}:{password}@{ip}:{port}"

        # Pola 2: Format standar ip:port:user:pass
        parts = line.split(':')
        if len(parts) == 4 and '.' in parts[0]:
            ip, port, user, password = parts
            return f"http://{user}:{password}@{ip}:{port}"

        # Pola 3: Format standar socks:ip:port:user:pass
        if len(parts) == 5 and parts[0].lower() in ['socks5', 'socks4']:
            proto, ip, port, user, password = parts
            return f"{proto.lower()}://{user}:{password}@{ip}:{port}"
            
        # Pola 4: Format sudah benar
        if '://' in line:
            return line

    except Exception:
        # Jika semua upaya gagal, lewati baris ini
        return None
        
    return None # Gagal mengenali format

def load_and_process_proxies(file_path):
    """Memuat proksi, menjalankan fungsi reparasi, dan menghapus duplikat."""
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error: '{file_path}' tidak ditemukan.[/bold red]")
        return []
    
    repaired_proxies = [p for p in (repair_and_reformat_proxy(line) for line in open(file_path)) if p]
    
    if not repaired_proxies:
        console.print(f"[bold red]Gagal memproses proksi. Pastikan format di '{file_path}' tidak kosong atau rusak total.[/bold red]")
        return []

    unique_proxies = sorted(list(set(repaired_proxies)))
    console.print(f"[green]Berhasil memperbaiki dan memuat {len(unique_proxies)} proksi unik.[/green]")
    
    # Menulis kembali ke file proxy.txt dengan format yang sudah benar
    with open(file_path, "w") as f:
        for proxy in unique_proxies: f.write(proxy + "\n")
    console.print("[cyan]File 'proxy.txt' telah diperbarui dengan format yang benar.[/cyan]")
    
    return unique_proxies

def check_proxy_universal(proxy):
    """Mengecek proksi (HTTP atau SOCKS) dengan metode ketat."""
    proxies_dict = {"http": proxy, "https": proxy}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    for url in CHECK_URLS:
        try:
            response = requests.get(url, proxies=proxies_dict, timeout=PROXY_TIMEOUT, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            return proxy, False, f"Gagal di {url.split('//')[1]}: {type(e).__name__}"
    return proxy, True, "OK (Lolos semua tes)"

# ... (Sisa kode dari versi advance sebelumnya tidak perlu diubah) ...
def run_concurrent_checks(proxies):
    good_proxies, failed_proxies_with_reason = [], []
    progress = Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), TimeRemainingColumn(), console=console)
    with Live(progress):
        task = progress.add_task("[cyan]Mengecek proksi (Mode Advance)...[/cyan]", total=len(proxies))
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_proxy = {executor.submit(check_proxy_universal, p): p for p in proxies}
            for future in as_completed(future_to_proxy):
                proxy, is_good, message = future.result()
                (good_proxies if is_good else failed_proxies_with_reason.append((proxy, message))).append(proxy) if is_good else None
                progress.update(task, advance=1)
    if failed_proxies_with_reason:
        with open(FAIL_PROXY_FILE, "w") as f:
            for p, _ in failed_proxies_with_reason: f.write(p + "\n")
        console.print(f"[yellow]Menyimpan {len(failed_proxies_with_reason)} proksi gagal ke '{FAIL_PROXY_FILE}'[/yellow]")
        console.print("\n[bold red]Laporan Diagnostik Kegagalan (Contoh):[/bold red]")
        error_table = Table(title="Analisis Error")
        error_table.add_column("Proksi (IP:Port)", style="cyan")
        error_table.add_column("Alasan Kegagalan", style="red")
        for proxy, reason in failed_pro_with_reason[:10]:
            proxy_display = proxy.split('@')[1] if '@' in proxy else proxy
            error_table.add_row(proxy_display, reason)
        console.print(error_table)
    return good_proxies

def distribute_proxies(proxies, paths):
    if not proxies or not paths: return
    console.print("\n[cyan]Mendistribusikan proksi valid...[/cyan]")
    for path in paths:
        if not os.path.isdir(path):
            console.print(f"[yellow]Peringatan: Path tidak ditemukan, dilewati: {path}[/yellow]")
            continue
        target_file_name = "proxies.txt" if os.path.exists(os.path.join(path, "proxies.txt")) else "proxy.txt"
        file_path = os.path.join(path, target_file_name)
        proxies_shuffled = random.sample(proxies, len(proxies))
        try:
            with open(file_path, "w") as f:
                for proxy in proxies_shuffled: f.write(proxy + "\n")
            console.print(f"  [green]✔[/green] Berhasil menulis ke [bold]{file_path}[/bold]")
        except IOError as e:
            console.print(f"  [red]✖[/red] Gagal menulis ke [bold]{file_path}[/bold]: {e}")

def run_full_process():
    print_header()
    if os.path.exists(PROXY_SOURCE_FILE):
        shutil.copy(PROXY_SOURCE_FILE, PROXY_BACKUP_FILE)
        console.print(f"[green]Backup dibuat: '{PROXY_BACKUP_FILE}'[/green]")
    
    console.print("[bold cyan]Langkah 1: Memperbaiki & Memproses Proksi...[/bold cyan]")
    proxies = load_and_process_proxies(PROXY_SOURCE_FILE)
    if not proxies:
        console.print("[bold red]Proses dihentikan.[/bold red]")
        return
    console.print("-" * 50)
    
    console.print("[bold cyan]Langkah 2: Mengecek Proksi (Mode Advance)...[/bold cyan]")
    good_proxies = run_concurrent_checks(proxies)
    if not good_proxies:
        console.print("[bold red]\nProses dihentikan: Tidak ada proksi yang berfungsi ditemukan.[/bold red]")
        return
        
    console.print(f"[bold green]\nDitemukan {len(good_proxies)} proksi yang berfungsi.[/bold green]")
    console.print("-" * 50)
    
    console.print("[bold cyan]Langkah 3: Memuat Path & Mendistribusikan...[/bold cyan]")
    paths = [line.strip() for line in open(PATHS_SOURCE_FILE) if line.strip()] if os.path.exists(PATHS_SOURCE_FILE) else []
    if not paths:
         console.print("[bold red]Proses dihentikan: Tidak ada path di 'paths.txt'.[/bold red]")
         return
    console.print(f"Menemukan {len(paths)} direktori target.")
    distribute_proxies(good_proxies, paths)
    console.print("\n[bold green]✅ Semua tugas selesai dengan sukses![/bold green]")

def main():
    while True:
        print_header()
        menu_table = Table(title="Main Menu", show_header=False, border_style="magenta")
        menu_table.add_column("Option", style="cyan", width=5)
        menu_table.add_column("Description")
        menu_table.add_row("[1]", "Jalankan Proses (Auto-Repair)")
        menu_table.add_row("[2]", "Kelola Path Target")
        menu_table.add_row("[3]", "Keluar")
        console.print(Align.center(menu_table))
        choice = Prompt.ask("Pilih opsi", choices=["1", "2", "3"], default="3")
        if choice == "1":
            run_full_process()
            Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "2":
             console.print("[yellow]Fitur 'Kelola Path' belum diimplementasikan di versi ini.[/yellow]")
             time.sleep(2)
        elif choice == "3":
            console.print("[bold cyan]Sampai jumpa![/bold cyan]")
            break

if __name__ == "__main__":
    main()
