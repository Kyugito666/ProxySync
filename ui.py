import time
from concurrent.futures import as_completed, ThreadPoolExecutor

from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (BarColumn, Progress, SpinnerColumn, TextColumn,
                           TimeRemainingColumn)
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

# Mengimpor semua fungsi inti dari run.py
import run

console = Console()

def print_header():
    """Menampilkan header aplikasi."""
    console.clear()
    title = Text("ProxySync Pro", style="bold cyan", justify="center")
    credits = Text("Created by Kyugito666 & Gemini AI", style="bold magenta", justify="center")
    header_table = Table.grid(expand=True)
    header_table.add_row(title)
    header_table.add_row(credits)
    console.print(Panel(header_table, border_style="green"))
    console.print()

def display_main_menu():
    """Menampilkan menu utama."""
    menu_table = Table(title="Main Menu", show_header=False, border_style="magenta")
    menu_table.add_column("Option", style="cyan", width=5)
    menu_table.add_column("Description")
    menu_table.add_row("[1]", "Konversi 'proxylist.txt' ke 'proxy.txt'")
    menu_table.add_row("[2]", "Jalankan Proses Penuh (Cek & Distribusi)")
    menu_table.add_row("[3]", "Kelola Path Target")
    menu_table.add_row("[4]", "Keluar")
    console.print(Align.center(menu_table))

def run_concurrent_checks_ui(proxies):
    """UI untuk menjalankan pengecekan proksi secara konkuren."""
    good_proxies, failed_proxies = [], []
    progress = Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), TimeRemainingColumn(), console=console
    )
    with Live(progress):
        task = progress.add_task("[cyan]Mengecek proksi (Tes Ketat dengan Ulang)...[/cyan]", total=len(proxies))
        with ThreadPoolExecutor(max_workers=run.MAX_WORKERS) as executor:
            future_to_proxy = {executor.submit(run.check_proxy_with_retry, p): p for p in proxies}
            for future in as_completed(future_to_proxy):
                proxy, is_good, message = future.result()
                (good_proxies.append(proxy) if is_good else failed_proxies.append(proxy))
                progress.update(task, advance=1)

    if failed_proxies:
        with open(run.FAIL_PROXY_FILE, "w") as f:
            for p in failed_proxies: f.write(p + "\n")
        console.print(f"[yellow]Menyimpan {len(failed_proxies)} proksi gagal ke '{run.FAIL_PROXY_FILE}'[/yellow]")
    return good_proxies


def run_full_process_ui():
    """Menjalankan seluruh alur kerja dari UI."""
    print_header()
    console.print("[bold cyan]Langkah 1: Mem-backup file proksi...[/bold cyan]")
    run.backup_file(run.PROXY_SOURCE_FILE, run.PROXY_BACKUP_FILE)
    console.print("-" * 40)

    console.print("[bold cyan]Langkah 2: Memuat dan membersihkan daftar proksi...[/bold cyan]")
    proxies = run.load_and_deduplicate_proxies(run.PROXY_SOURCE_FILE)
    if not proxies:
        console.print("[bold red]Proses dihentikan: 'proxy.txt' kosong atau tidak ditemukan.[/bold red]")
        return
    console.print(f"Menemukan {len(proxies)} proksi unik untuk dites.")
    console.print("-" * 40)

    console.print("[bold cyan]Langkah 3: Mengecek proksi yang aktif...[/bold cyan]")
    good_proxies = run_concurrent_checks_ui(proxies)
    if not good_proxies:
        console.print("[bold red]Proses dihentikan: Tidak ada proksi yang berfungsi ditemukan.[/bold red]")
        return
    console.print(f"[bold green]Ditemukan {len(good_proxies)} proksi yang berfungsi.[/bold green]")
    console.print("-" * 40)

    console.print("[bold cyan]Langkah 4: Memuat path target...[/bold cyan]")
    paths = run.load_paths(run.PATHS_SOURCE_FILE)
    if not paths:
        console.print("[bold red]Proses dihentikan: Tidak ada path valid di 'paths.txt'.[/bold red]")
        return
    
    run.distribute_proxies(good_proxies, paths)
    console.print("\n[bold green]✅ Semua tugas selesai dengan sukses![/bold green]")

def manage_paths_menu_ui():
    # Fungsi ini tidak berubah dari versi asli, hanya memanggil fungsi dari run.py
    console.print("[yellow]Fitur 'Kelola Path' belum diimplementasikan di versi UI terpisah ini.[/yellow]")
    time.sleep(2)

def main():
    """Fungsi utama untuk menjalankan aplikasi."""
    while True:
        print_header()
        display_main_menu()
        choice = Prompt.ask("Pilih opsi", choices=["1", "2", "3", "4"], default="4")

        if choice == "1":
            run.convert_proxylist_to_http()
            Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "2":
            run_full_process_ui()
            Prompt.ask("\n[bold]Tekan Enter untuk kembali...[/bold]")
        elif choice == "3":
            manage_paths_menu_ui()
        elif choice == "4":
            console.print("[bold cyan]Sampai jumpa![/bold cyan]")
            break

if __name__ == "__main__":
    main()
      
