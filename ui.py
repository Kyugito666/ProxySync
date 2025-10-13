import time
import requests
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
    menu_table.add_row("[1]", "Unduh Proksi dari Daftar API")
    menu_table.add_row("[2]", "Konversi 'proxylist.txt'")
    menu_table.add_row("[3]", "Jalankan Tes Akurat & Distribusi")
    menu_table.add_row("[4]", "Kelola Path Target")
    menu_table.add_row("[5]", "Keluar")
    console.print(Align.center(menu_table))
    return Prompt.ask("Pilih opsi", choices=["1", "2", "3", "4", "5"], default="5")

def fetch_from_api(url):
    """Fungsi pembantu untuk mengunduh dari satu URL API dengan mekanisme backoff."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=45)
            response.raise_for_status() # Akan memicu error untuk status 4xx/5xx
            content = response.text.strip()
            if content:
                return url, content.splitlines(), None # Sukses
            error_message = "API tidak mengembalikan konten"

        except requests.exceptions.HTTPError as e:
            # --- LOGIKA BARU: Khusus menangani error 429 ---
            if e.response.status_code == 429:
                wait_time = 10 * (attempt + 1) # 10s, 20s, 30s
                console.print(f"[bold yellow]Rate limit terdeteksi. Menunggu {wait_time} detik sebelum mencoba lagi...[/bold yellow]")
                time.sleep(wait_time)
                error_message = str(e) # Simpan pesan error untuk percobaan terakhir
                continue # Lanjutkan ke percobaan berikutnya
            else:
                error_message = str(e) # Error HTTP lain
                break # Gagal karena alasan lain, hentikan retry

        except requests.exceptions.RequestException as e:
            error_message = str(e) # Error koneksi/timeout
            time.sleep(3) # Beri jeda singkat untuk error koneksi

    # Jika semua percobaan gagal, kembalikan error terakhir
    return url, [], error_message

def run_concurrent_api_downloads(urls, max_workers):
    """Menampilkan progress bar untuk mengunduh dari banyak API."""
    all_proxies = []
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    )
    with Live(progress):
        task = progress.add_task("[cyan]Mengunduh dari semua API...[/cyan]", total=len(urls))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(fetch_from_api, url): url for url in urls}
            for future in as_completed(future_to_url):
                url, proxies, error = future.result()
                if error:
                    error_msg = str(error).splitlines()[0] 
                    console.print(f"[bold red]✖ GAGAL FINAL[/bold red] dari {url[:50]}... [dim]({error_msg})[/dim]")
                else:
                    console.print(f"[green]✔ Berhasil[/green] dari {url[:50]}... ({len(proxies)} proksi)")
                    all_proxies.extend(proxies)
                progress.update(task, advance=1)

    return all_proxies


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
