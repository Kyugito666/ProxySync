import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.live import Live

console = Console()

def print_header():
    """Menampilkan header aplikasi."""
    console.clear()
    title = Text("ProxySync Pro - Accurate Test", style="bold green", justify="center")
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
    menu_table.add_row("[1]", "Konversi 'proxylist.txt'")
    menu_table.add_row("[2]", "Jalankan Tes Akurat & Distribusi")
    menu_table.add_row("[3]", "Kelola Path Target")
    menu_table.add_row("[4]", "Keluar")
    console.print(Align.center(menu_table))
    return Prompt.ask("Pilih opsi", choices=["1", "2", "3", "4"], default="4")

def run_concurrent_checks_display(proxies, check_function, max_workers, fail_file):
    """Menampilkan progress bar dan laporan diagnostik."""
    good_proxies, failed_proxies_with_reason = [], []
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    )
    with Live(progress):
        task = progress.add_task("[cyan]Menjalankan Tes Akurat...[/cyan]", total=len(proxies))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_proxy = {executor.submit(check_function, p): p for p in proxies}
            for future in as_completed(future_to_proxy):
                proxy, is_good, message = future.result()
                if is_good:
                    good_proxies.append(proxy)
                else:
                    failed_proxies_with_reason.append((proxy, message))
                progress.update(task, advance=1)

    if failed_proxies_with_reason:
        with open(fail_file, "w") as f:
            for p, _ in failed_proxies_with_reason: f.write(p + "\n")
        console.print(f"\n[yellow]Menyimpan {len(failed_proxies_with_reason)} proksi gagal ke '{fail_file}'[/yellow]")

        # Laporan Diagnostik
        error_table = Table(title="Laporan Diagnostik Kegagalan (Contoh)")
        error_table.add_column("Proksi (IP:Port)", style="cyan")
        error_table.add_column("Alasan Kegagalan", style="red")
        for proxy, reason in failed_proxies_with_reason[:10]:
            proxy_display = proxy.split('@')[1] if '@' in proxy else proxy
            error_table.add_row(proxy_display, reason)
        console.print(error_table)
    return good_proxies

def manage_paths_menu_display():
    """UI untuk mengelola paths.txt."""
    console.print("[yellow]Fitur 'Kelola Path' belum diimplementasikan.[/yellow]")
    time.sleep(2)
