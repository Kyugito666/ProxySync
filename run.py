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

# --- Configuration ---
PROXY_SOURCE_FILE = "proxy.txt"
PATHS_SOURCE_FILE = "paths.txt"
FAIL_PROXY_FILE = "fail_proxy.txt"
PROXY_BACKUP_FILE = "proxy_backup.txt"
PROXY_TIMEOUT = 10
MAX_WORKERS = 20  # Adjust based on your system's capability

# --- UI and Console Initialization ---
console = Console()

def print_header():
    """Displays the application header."""
    console.clear()
    title = Text("ProxySync Pro", style="bold cyan", justify="center")
    credits = Text("Created by Kyugito666 & Gemini AI", style="bold magenta", justify="center")
    header_table = Table.grid(expand=True)
    header_table.add_row(title)
    header_table.add_row(credits)
    console.print(Panel(header_table, border_style="green"))
    console.print()

# --- Core Logic ---
def load_and_deduplicate_proxies(file_path):
    """Loads proxies from a file and removes duplicates."""
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error: '{file_path}' not found.[/bold red]")
        return []

    with open(file_path, "r") as f:
        proxies = [line.strip() for line in f if line.strip()]

    if not proxies:
        console.print(f"[yellow]'{file_path}' is empty.[/yellow]")
        return []

    unique_proxies = sorted(list(set(proxies)))
    num_duplicates = len(proxies) - len(unique_proxies)

    if num_duplicates > 0:
        console.print(f"[yellow]Removed {num_duplicates} duplicate proxies.[/yellow]")

    # Overwrite the original file with deduplicated list
    with open(file_path, "w") as f:
        for proxy in unique_proxies:
            f.write(proxy + "\n")

    return unique_proxies

def load_paths(file_path):
    """Loads target paths from a file."""
    if not os.path.exists(file_path):
        console.print(f"[bold red]Error: Path file '{file_path}' not found.[/bold red]")
        return []
    with open(file_path, "r") as f:
        return [line.strip() for line in f if line.strip() and os.path.isdir(line.strip())]

def backup_file(file_path, backup_path):
    """Creates a backup of a given file."""
    if os.path.exists(file_path):
        shutil.copy(file_path, backup_path)
        console.print(f"[green]Backup created: '{file_path}' -> '{backup_path}'[/green]")

def format_proxy(proxy):
    """Ensures proxy URL is correctly formatted."""
    if not (proxy.startswith("http://") or proxy.startswith("https://")):
        return f"http://{proxy}"
    return proxy

def check_proxy(proxy):
    """Checks a single proxy and returns its status."""
    proxy_url = format_proxy(proxy)
    try:
        response = requests.get(
            "http://ifconfig.me/ip",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=PROXY_TIMEOUT
        )
        if response.status_code == 200 and response.text.strip():
            return proxy, True, response.text.strip()
        return proxy, False, f"Status Code: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return proxy, False, "Connection Error"

def check_proxies_concurrently(proxies):
    """Checks a list of proxies using multiple threads and displays progress."""
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
        task = progress.add_task("[cyan]Checking proxies...", total=len(proxies))
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(check_proxy, p) for p in proxies]
            for future in as_completed(futures):
                proxy, is_good, message = future.result()
                if is_good:
                    good_proxies.append(proxy)
                else:
                    failed_proxies.append(proxy)
                progress.update(task, advance=1)

    # Save failed proxies
    if failed_proxies:
        with open(FAIL_PROXY_FILE, "w") as f:
            for p in failed_proxies:
                f.write(p + "\n")
        console.print(f"[yellow]Saved {len(failed_proxies)} failed proxies to '{FAIL_PROXY_FILE}'[/yellow]")

    return good_proxies

def distribute_proxies(proxies, paths):
    """Saves a shuffled list of proxies to each target path."""
    if not proxies or not paths:
        console.print("[red]No valid proxies or paths to distribute.[/red]")
        return

    console.print("\n[cyan]Distributing valid proxies to target directories...[/cyan]")
    for path in paths:
        if not os.path.isdir(path):
            console.print(f"[yellow]Warning: Path not found, skipping: {path}[/yellow]")
            continue
        
        # --- PERUBAHAN DI SINI ---
        # Mencari nama file proxy secara otomatis
        file_name = "proxy.txt"
        if os.path.exists(os.path.join(path, "proxies.txt")):
            file_name = "proxies.txt"
        elif os.path.exists(os.path.join(path, "proxy.txt")):
            file_name = "proxy.txt"
        
        file_path = os.path.join(path, file_name)
        
        # Buat salinan daftar proxy untuk memastikan pengacakan yang independen untuk setiap file.
        proxies_shuffled = proxies[:]
        random.shuffle(proxies_shuffled)

        try:
            with open(file_path, "w") as f:
                # Tulis dari daftar yang sudah diacak secara independen
                for proxy in proxies_shuffled:
                    f.write(proxy + "\n")
            console.print(f"  [green]✔[/green] Successfully wrote to [bold]{file_path}[/bold]")
        except IOError as e:
            console.print(f"  [red]✖[/red] Failed to write to [bold]{file_path}[/bold]: {e}")


# --- Menu and UI Functions ---
def display_main_menu():
    """Displays the main menu options in a formatted table."""
    menu_table = Table(title="Main Menu", show_header=False, border_style="magenta")
    menu_table.add_column("Option", style="cyan", width=5)
    menu_table.add_column("Description")
    menu_table.add_row("[1]", "Run Full Process (Backup, Check, Distribute)")
    menu_table.add_row("[2]", "Manage Target Paths")
    menu_table.add_row("[3]", "Exit")
    console.print(Align.center(menu_table))

def manage_paths_menu():
    """UI for viewing and managing the paths.txt file."""
    while True:
        print_header()
        paths = load_paths(PATHS_SOURCE_FILE)
        table = Table(title=f"Target Paths ({len(paths)} found)", border_style="yellow")
        table.add_column("#", style="dim", width=4)
        table.add_column("Directory Path")

        for i, path in enumerate(paths):
            status = "✔ Found" if os.path.exists(path) else "✖ Not Found"
            color = "green" if os.path.exists(path) else "red"
            table.add_row(str(i + 1), f"[{color}]{path} ({status})[/{color}]")

        console.print(table)
        console.print("\n[cyan][A][/cyan]dd a new path | [cyan][D][/cyan]elete a path | [cyan][B][/cyan]ack to main menu")
        choice = Prompt.ask("Choose an option", choices=["A", "D", "B"], default="B").upper()

        if choice == "A":
            new_path = Prompt.ask("Enter the full path to add").strip()
            if os.path.isdir(new_path):
                with open(PATHS_SOURCE_FILE, "a") as f:
                    f.write(f"\n{new_path}")
                console.print(f"[green]Path '{new_path}' added.[/green]")
            else:
                console.print(f"[red]Error: '{new_path}' is not a valid directory.[/red]")
            time.sleep(1.5)

        elif choice == "D":
            if not paths:
                console.print("[yellow]No paths to delete.[/yellow]")
                time.sleep(1.5)
                continue
            try:
                num_to_delete = int(Prompt.ask("Enter the # of the path to delete"))
                if 1 <= num_to_delete <= len(paths):
                    deleted_path = paths.pop(num_to_delete - 1)
                    with open(PATHS_SOURCE_FILE, "w") as f:
                        for p in paths:
                            f.write(p + "\n")
                    console.print(f"[green]Path '{deleted_path}' removed.[/green]")
                else:
                    console.print("[red]Invalid number.[/red]")
            except ValueError:
                console.print("[red]Please enter a valid number.[/red]")
            time.sleep(1.5)

        elif choice == "B":
            break

def run_full_process():
    """Executes the entire proxy processing workflow."""
    print_header()

    # Step 1: Backup proxy file
    console.print("[bold cyan]Step 1: Backing up proxy file...[/bold cyan]")
    backup_file(PROXY_SOURCE_FILE, PROXY_BACKUP_FILE)
    console.print("-" * 30)

    # Step 2: Load and deduplicate proxies
    console.print("[bold cyan]Step 2: Loading and cleaning proxy list...[/bold cyan]")
    proxies = load_and_deduplicate_proxies(PROXY_SOURCE_FILE)
    if not proxies:
        console.print("[bold red]Process stopped: No proxies to check.[/bold red]")
        return
    console.print(f"Found {len(proxies)} unique proxies to test.")
    console.print("-" * 30)

    # Step 3: Check proxies
    console.print("[bold cyan]Step 3: Checking which proxies are live...[/bold cyan]")
    good_proxies = check_proxies_concurrently(proxies)
    if not good_proxies:
        console.print("[bold red]Process stopped: No working proxies found.[/bold red]")
        return
    console.print(f"[bold green]Found {len(good_proxies)} working proxies.[/bold green]")
    console.print("-" * 30)

    # Step 4: Load paths
    console.print("[bold cyan]Step 4: Loading target paths...[/bold cyan]")
    paths = load_paths(PATHS_SOURCE_FILE)
    if not paths:
        console.print("[bold red]Process stopped: No valid paths found in 'paths.txt'.[/bold red]")
        return
    console.print(f"Found {len(paths)} valid target directories.")
    console.print("-" * 30)

    # Step 5: Distribute proxies
    distribute_proxies(good_proxies, paths)

    console.print("\n[bold green]✅ All tasks completed successfully![/bold green]")

# --- Main Application Loop ---
def main():
    """Main function to run the application loop."""
    while True:
        print_header()
        display_main_menu()
        choice = Prompt.ask("Select an option", choices=["1", "2", "3"], default="3")

        if choice == "1":
            run_full_process()
            Prompt.ask("\n[bold]Press Enter to return to the main menu...[/bold]")
        elif choice == "2":
            manage_paths_menu()
        elif choice == "3":
            console.print("[bold cyan]Goodbye![/bold cyan]")
            break

if __name__ == "__main__":
    main()
