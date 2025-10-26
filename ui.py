print("DEBUG: Starting ui.py execution", flush=True)
import time
import requests
import re
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
    MofNCompleteColumn,
)
from rich.live import Live
from rich.layout import Layout
from rich.box import ROUNDED, DOUBLE, HEAVY

try:
    import questionary
    QUESTIONARY_AVAILABLE = True
except ImportError:
    QUESTIONARY_AVAILABLE = False

console = Console()

def print_header():
    """Menampilkan header aplikasi."""
    console.clear()
    
    # Simple header tanpa ASCII art yang ribet
    console.print()
    console.print(Panel(
        "[bold cyan]PROXYSYNC v3.0[/bold cyan]\n"
        "[dim]Proxy Testing & Distribution System[/dim]",
        border_style="cyan",
        box=ROUNDED,
        padding=(1, 2)
    ))
    console.print()

def display_main_menu():
    """Menampilkan menu utama."""
    
    console.print("[bold cyan]MAIN MENU[/bold cyan]")
    console.print()
    
    menu_display = [
        "1. Sinkronisasi IP Otorisasi Webshare",
        "2. Unduh Proksi dari Daftar API",
        "3. Konversi Format Proxy List",
        "4. Jalankan Tes Akurat & Distribusi",
        "5. Kelola Path Target Distribusi",
        "6. Keluar dari Aplikasi",
    ]
    
    if QUESTIONARY_AVAILABLE:
        selected_option = questionary.select(
            "Pilih operasi:",
            choices=menu_display,
            use_arrow_keys=True,
            pointer=">",
            style=questionary.Style([
                ('qmark', 'fg:#00ffff bold'),
                ('question', 'fg:#ffffff bold'),
                ('answer', 'fg:#00ff00 bold'),
                ('pointer', 'fg:#ffff00 bold'),
                ('highlighted', 'fg:#ffff00 bold'),
                ('selected', 'fg:#00ff00'),
            ])
        ).ask()
        
        if selected_option is None:
            return "6"
        
        option_map = {
            menu_display[0]: "1",
            menu_display[1]: "2",
            menu_display[2]: "3",
            menu_display[3]: "4",
            menu_display[4]: "5",
            menu_display[5]: "6",
        }
        return option_map.get(selected_option, "6")
    else:
        console.print(Panel(
            "[yellow]Enhanced UI tidak tersedia[/yellow]\n"
            "[dim]Install 'questionary' untuk navigasi arrow key:[/dim]\n"
            "[cyan]pip install questionary[/cyan]",
            border_style="yellow",
            box=ROUNDED
        ))
        console.print()
        
        menu_table = Table(box=ROUNDED, border_style="cyan", show_header=False, padding=(0, 1))
        menu_table.add_column("No", style="bold yellow", width=6)
        menu_table.add_column("Menu", style="white")
        
        for idx, option in enumerate(menu_display, 1):
            menu_table.add_row(f"[{idx}]", option)
        
        console.print(menu_table)
        
        choice = Prompt.ask(
            "\nMasukkan pilihan",
            choices=["1", "2", "3", "4", "5", "6"],
            default="6"
        )
        return choice

def fetch_from_api(url: str, api_key: str | None):
    """Fungsi pembantu untuk mengunduh dari satu URL API."""
    max_retries = 3
    headers = {} 
    if api_key:
        headers['Authorization'] = f"Token {api_key}" 

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=60) 
            if response.status_code == 429:
                wait_time = 15 * (attempt + 1) 
                console.print(f"[yellow]Rate limit terdeteksi. Menunggu {wait_time} detik...[/yellow]")
                time.sleep(wait_time)
                continue 
            response.raise_for_status() 
            content = response.text.strip()
            if content:
                if '\n' in content or re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d+", content.splitlines()[0]):
                    return url, content.splitlines(), None
                else:
                    error_message = "Respons tidak valid (bukan proxy list)"
                    break 
            else:
                error_message = "Respons kosong dari server"
                break 
        except requests.exceptions.HTTPError as e:
             error_message = f"HTTP {e.response.status_code} Error"
             break 
        except requests.exceptions.RequestException as e:
            error_message = f"Koneksi gagal: {str(e)[:50]}"
            if attempt < max_retries - 1:
                console.print(f"[yellow]Koneksi gagal, retry dalam 5 detik... ({attempt+1}/{max_retries})[/yellow]")
                time.sleep(5) 
    return url, [], error_message

def run_sequential_api_downloads(download_targets: list[tuple[str, str | None]]):
    """Menjalankan unduhan API satu per satu dengan progress tracking."""
    all_proxies = []
    
    progress = Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console
    )
    
    total_targets = len(download_targets)
    
    console.print(f"[cyan]Memulai download dari {total_targets} sumber API[/cyan]\n")
    
    with Live(progress, console=console, refresh_per_second=10):
        task = progress.add_task("[cyan]Mengunduh proxy list...", total=total_targets)
        
        for i, (url, api_key) in enumerate(download_targets, 1):
            progress.update(task, description=f"[cyan]Download {i}/{total_targets}")
            _, proxies, error = fetch_from_api(url, api_key) 
            
            # Tampilkan URL yang lebih pendek
            url_display = url[:50] + "..." if len(url) > 50 else url
            
            if error:
                error_msg = str(error)[:40]
                console.print(f"[red]FAIL[/red] {url_display} - {error_msg}")
            else:
                console.print(f"[green]OK[/green]   {url_display} - {len(proxies)} proxies")
                all_proxies.extend(proxies)
            
            progress.update(task, advance=1)
            
            if i < total_targets:
                time.sleep(5)
    
    console.print()
    return all_proxies

def run_concurrent_checks_display(proxies, check_function, max_workers, fail_file):
    """Menampilkan progress bar untuk testing proxy."""
    good_proxies, failed_proxies_with_reason = [], []
    
    console.print(f"[cyan]Memulai testing {len(proxies)} proxies[/cyan]")
    console.print(f"[dim]Workers: {max_workers} threads | Timeout: 25s per proxy[/dim]\n")
    
    progress = Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=50, style="cyan", complete_style="green"),
        MofNCompleteColumn(),
        TextColumn("•"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console
    )
    
    with Live(progress, console=console, refresh_per_second=10):
        task = progress.add_task("[cyan]Testing proxies via GitHub API...", total=len(proxies))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_proxy = {executor.submit(check_function, p): p for p in proxies}
            
            for future in as_completed(future_to_proxy):
                proxy, is_good, message = future.result()
                
                if is_good:
                    good_proxies.append(proxy)
                else:
                    failed_proxies_with_reason.append((proxy, message))
                
                progress.update(task, advance=1)
    
    console.print()
    
    # Results summary
    summary_table = Table(box=ROUNDED, border_style="cyan", show_header=True, header_style="bold white")
    summary_table.add_column("Status", justify="center", width=15)
    summary_table.add_column("Count", justify="center", width=10)
    summary_table.add_column("Percentage", justify="center", width=15)
    
    total = len(proxies)
    success_count = len(good_proxies)
    fail_count = len(failed_proxies_with_reason)
    success_pct = (success_count / total * 100) if total > 0 else 0
    fail_pct = (fail_count / total * 100) if total > 0 else 0
    
    summary_table.add_row("[green]PASSED[/green]", f"[green]{success_count}[/green]", f"[green]{success_pct:.1f}%[/green]")
    summary_table.add_row("[red]FAILED[/red]", f"[red]{fail_count}[/red]", f"[red]{fail_pct:.1f}%[/red]")
    summary_table.add_row("[cyan]TOTAL[/cyan]", f"{total}", "100%")
    
    console.print(Panel(summary_table, title="[bold]Test Results Summary[/bold]", border_style="cyan", box=ROUNDED))
    
    if failed_proxies_with_reason:
        with open(fail_file, "w") as f:
            for p, _ in failed_proxies_with_reason:
                f.write(p + "\n")
        
        console.print(f"\n[yellow]{fail_count} failed proxies saved to '{fail_file}'[/yellow]")
        
        # Error breakdown table (top 10 only)
        if len(failed_proxies_with_reason) > 0:
            error_table = Table(
                title="[bold red]Failure Analysis (Top 10)[/bold red]",
                box=ROUNDED,
                border_style="red",
                show_header=True,
                header_style="bold white"
            )
            error_table.add_column("Proxy", style="cyan", width=40)
            error_table.add_column("Reason", style="yellow")
            
            for proxy, reason in failed_proxies_with_reason[:10]:
                proxy_display = proxy.split('@')[1] if '@' in proxy else proxy
                if len(proxy_display) > 35:
                    proxy_display = proxy_display[:32] + "..."
                error_table.add_row(proxy_display, reason)
            
            console.print()
            console.print(error_table)
    
    return good_proxies

def manage_paths_menu_display():
    """Placeholder untuk menu manage paths."""
    console.print(Panel(
        "[yellow]Feature Coming Soon[/yellow]\n\n"
        "[dim]Fitur 'Kelola Path Target' sedang dalam pengembangan.\n"
        "Saat ini Anda dapat mengedit file '../config/paths.txt' secara manual.[/dim]",
        title="[bold]Under Construction[/bold]",
        border_style="yellow",
        box=ROUNDED
    ))
    time.sleep(3)
