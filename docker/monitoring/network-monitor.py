#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mitmproxy>=10.1.0",
#     "rich>=13.7.0",
# ]
# ///

"""
Interactive Network Monitor and Firewall for Docker Container

This script provides real-time network monitoring and access control
with different permission levels (allow, deny, prompt, etc.).
"""

import json
import sys
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Literal

from mitmproxy import http
from mitmproxy.tools import main as mitmproxy_main
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

# Permission types
PermissionType = Literal["allow", "deny", "prompt", "allow-domain", "deny-domain"]

# Config file location
CONFIG_FILE = Path.home() / "docker-agent-data" / "network-rules.json"
LOG_FILE = Path.home() / "docker-agent-data" / "network-access.log"
PENDING_FILE = Path.home() / "docker-agent-data" / "network-pending.json"

console = Console()


class NetworkFirewall:
    """Manages network access rules and permissions"""

    def __init__(self):
        self.rules: dict[str, PermissionType] = {}
        self.stats = defaultdict(int)
        self.recent_requests = []
        self.pending_requests = []  # Requests awaiting approval via web UI
        self.max_recent = 50
        self.max_pending = 100
        self.lock = threading.Lock()
        self.rules_mtime = 0.0  # Track rules file modification time for auto-reload
        self.pending_mtime = 0.0  # Track pending file modification time for auto-reload
        self.load_rules()
        self.load_pending()

    def load_rules(self):
        """Load rules from config file"""
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    self.rules = json.load(f)
                # Update modification time after successful load
                self.rules_mtime = CONFIG_FILE.stat().st_mtime
                console.print(f"[green]Loaded {len(self.rules)} network rules[/green]")
            except Exception as e:
                console.print(f"[red]Error loading rules: {e}[/red]")

    def reload_rules_if_changed(self):
        """Reload rules if the config file has been modified (e.g., by web UI)"""
        if not CONFIG_FILE.exists():
            return

        try:
            current_mtime = CONFIG_FILE.stat().st_mtime
            if current_mtime > self.rules_mtime:
                # File was modified, reload rules
                with self.lock:
                    with open(CONFIG_FILE) as f:
                        self.rules = json.load(f)
                    self.rules_mtime = current_mtime
                    # Silent reload - don't spam console
        except Exception:
            # Ignore errors during reload check (file might be mid-write)
            pass

    def reload_pending_if_changed(self):
        """Reload pending requests if the file has been modified (e.g., by web UI)"""
        if not PENDING_FILE.exists():
            return

        try:
            current_mtime = PENDING_FILE.stat().st_mtime
            if current_mtime > self.pending_mtime:
                # File was modified, reload pending requests
                with self.lock:
                    with open(PENDING_FILE) as f:
                        self.pending_requests = json.load(f)
                    self.pending_mtime = current_mtime
                    # Silent reload - don't spam console
        except Exception:
            # Ignore errors during reload check (file might be mid-write)
            pass

    def save_rules(self):
        """Save rules to config file"""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.rules, f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving rules: {e}[/red]")

    def load_pending(self):
        """Load pending requests from file"""
        PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        if PENDING_FILE.exists():
            try:
                with open(PENDING_FILE) as f:
                    self.pending_requests = json.load(f)
                # Update modification time after successful load
                self.pending_mtime = PENDING_FILE.stat().st_mtime
            except Exception as e:
                console.print(f"[red]Error loading pending requests: {e}[/red]")
                self.pending_requests = []

    def save_pending(self):
        """Save pending requests to file"""
        try:
            with open(PENDING_FILE, "w") as f:
                json.dump(self.pending_requests, f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving pending requests: {e}[/red]")

    def log_request(self, host: str, method: str, path: str, decision: str):
        """Log network request"""
        with self.lock:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().isoformat()
            log_entry = f"{timestamp} | {decision:10s} | {method:6s} | {host}{path}\n"

            with open(LOG_FILE, "a") as f:
                f.write(log_entry)

            # Keep recent requests in memory
            self.recent_requests.append(
                {
                    "timestamp": timestamp,
                    "host": host,
                    "method": method,
                    "path": path,
                    "decision": decision,
                }
            )
            if len(self.recent_requests) > self.max_recent:
                self.recent_requests.pop(0)

            # Update stats
            self.stats[decision] += 1
            self.stats["total"] += 1

    def check_permission(self, host: str, url: str, method: str, path: str) -> bool:
        """
        Check if request should be allowed.

        Security model: DEFAULT DENY
        - Only explicitly allowed requests are permitted
        - All other requests are denied and queued for approval
        """
        # Reload rules if modified (e.g., by web UI)
        self.reload_rules_if_changed()

        # Check exact URL match
        if url in self.rules:
            rule = self.rules[url]
            if rule == "allow":
                self.log_request(host, method, path, "ALLOW")
                return True
            elif rule == "deny":
                self.log_request(host, method, path, "DENY")
                return False

        # Check domain-level rules
        if host in self.rules:
            rule = self.rules[host]
            if rule in ("allow", "allow-domain"):
                self.log_request(host, method, path, "ALLOW")
                return True
            elif rule in ("deny", "deny-domain"):
                self.log_request(host, method, path, "DENY")
                return False

        # Check wildcard domain rules (*.example.com)
        domain_parts = host.split(".")
        for i in range(len(domain_parts)):
            wildcard = "*." + ".".join(domain_parts[i:])
            if wildcard in self.rules:
                rule = self.rules[wildcard]
                if rule in ("allow", "allow-domain"):
                    self.log_request(host, method, path, "ALLOW")
                    return True
                elif rule in ("deny", "deny-domain"):
                    self.log_request(host, method, path, "DENY")
                    return False

        # Default: DENY and queue for approval (fail-safe)
        return self.prompt_user(host, url, method, path)

    def add_pending_request(self, host: str, url: str, method: str, path: str):
        """Add request to pending approval queue"""
        # Reload pending list if modified (e.g., by web UI)
        self.reload_pending_if_changed()

        with self.lock:
            # Check if already in pending (avoid duplicates)
            for req in self.pending_requests:
                if req["host"] == host and req["url"] == url:
                    return

            # Add to pending queue
            pending_req = {
                "host": host,
                "url": url,
                "method": method,
                "path": path,
                "timestamp": datetime.now().isoformat(),
            }
            self.pending_requests.append(pending_req)

            # Keep only most recent pending requests
            if len(self.pending_requests) > self.max_pending:
                self.pending_requests = self.pending_requests[-self.max_pending :]

            # Save to file
            self.save_pending()

    def prompt_user(self, host: str, url: str, method: str, path: str) -> bool:
        """
        Handle request without explicit rule: DEFAULT DENY.

        For security, all requests not explicitly allowed are denied.
        The request is logged and queued for user approval via web UI.
        """
        self.add_pending_request(host, url, method, path)
        self.log_request(host, method, path, "PENDING")
        return False  # SECURITY: Deny by default until explicitly approved

    def load_stats_from_log(self) -> dict[str, int]:
        """Load statistics from log file (for CLI mode)"""
        stats = defaultdict(int)

        if not LOG_FILE.exists():
            return dict(stats)

        try:
            with open(LOG_FILE) as f:
                for line in f:
                    # Parse log line: "timestamp | decision | method | url"
                    parts = line.strip().split("|")
                    if len(parts) >= 2:
                        decision = parts[1].strip()
                        stats[decision] += 1
                        stats["total"] += 1
        except Exception:
            pass

        return dict(stats)

    def load_recent_from_log(self, limit: int = 10) -> list[dict]:
        """Load recent requests from log file (for CLI mode)"""
        if not LOG_FILE.exists():
            return []

        try:
            # Read last portion of file for efficiency
            import os

            file_size = os.path.getsize(LOG_FILE)
            if file_size == 0:
                return []

            read_size = min(file_size, 100 * 1024)  # 100KB max

            with open(LOG_FILE, "rb") as f:
                f.seek(max(0, file_size - read_size))
                data = f.read()

            # Decode and parse lines
            text = data.decode("utf-8", errors="ignore")
            lines = [line for line in text.split("\n") if line.strip()][-limit:]

            requests = []
            for line in lines:
                # Parse: "timestamp | decision | method | host/path"
                parts = line.strip().split("|")
                if len(parts) >= 4:
                    requests.append(
                        {
                            "timestamp": parts[0].strip(),
                            "decision": parts[1].strip(),
                            "method": parts[2].strip(),
                            "host": parts[3].strip(),
                        }
                    )

            return requests

        except Exception:
            return []

    def get_stats_table(self) -> Table:
        """Generate statistics table (loads from log file if in CLI mode)"""
        table = Table(title="Network Access Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green")

        # In CLI mode, in-memory stats will be empty - load from log file
        stats_to_show = self.stats if self.stats else self.load_stats_from_log()

        for key, value in sorted(stats_to_show.items()):
            table.add_row(key.title(), str(value))

        return table

    def get_recent_table(self) -> Table:
        """Generate recent requests table (loads from log file if in CLI mode)"""
        table = Table(title="Recent Requests (Last 10)")
        table.add_column("Time", style="cyan")
        table.add_column("Decision", style="yellow")
        table.add_column("Method", style="blue")
        table.add_column("Host", style="green")

        # In CLI mode, in-memory requests will be empty - load from log file
        requests_to_show = (
            self.recent_requests[-10:] if self.recent_requests else self.load_recent_from_log(10)
        )

        for req in requests_to_show:
            time_str = (
                req["timestamp"].split("T")[1][:8]
                if "T" in req["timestamp"]
                else req["timestamp"][:8]
            )
            table.add_row(time_str, req["decision"], req["method"], req["host"])

        return table


# Global firewall instance
firewall = NetworkFirewall()


class FirewallAddon:
    """mitmproxy addon for network filtering"""

    addons = []  # No nested addons (required by mitmproxy)

    def request(self, flow: http.HTTPFlow) -> None:
        """Intercept and filter HTTP requests"""
        host = flow.request.pretty_host
        method = flow.request.method
        path = flow.request.path
        url = flow.request.url

        if not firewall.check_permission(host, url, method, path):
            flow.response = http.Response.make(
                403, b"Access denied by network firewall", {"Content-Type": "text/plain"}
            )


def run_proxy():
    """Run the mitmproxy server"""
    console.print("[bold green]Starting Network Monitor & Firewall[/bold green]")
    console.print(f"[cyan]Rules file:[/cyan] {CONFIG_FILE}")
    console.print(f"[cyan]Log file:[/cyan] {LOG_FILE}")
    console.print("[cyan]Proxy listening on:[/cyan] 0.0.0.0:8080")
    console.print(
        "\n[yellow]Configure Docker to use HTTP proxy: http://host.docker.internal:8080[/yellow]"
    )
    console.print(
        "[yellow]Set HTTPS_PROXY and HTTP_PROXY environment variables in container[/yellow]\n"
    )

    # Run mitmproxy with the firewall addon
    sys.argv = [
        "mitmproxy",
        "--mode",
        "regular",
        "--listen-host",
        "0.0.0.0",
        "--listen-port",
        "8080",
        "--set",
        "confdir=~/.mitmproxy",
        "-s",
        __file__,  # Load this script as addon
    ]

    # Start in quiet mode if running as addon
    if len(sys.argv) > 1 and sys.argv[1] == "--addon-mode":
        sys.argv.extend(["--quiet"])

    mitmproxy_main.mitmproxy()


def show_stats():
    """Show current statistics and rules"""
    console.clear()
    console.print(firewall.get_stats_table())
    console.print()
    console.print(firewall.get_recent_table())
    console.print()

    # Show active rules
    if firewall.rules:
        rules_table = Table(title=f"Active Rules ({len(firewall.rules)})")
        rules_table.add_column("Target", style="cyan")
        rules_table.add_column("Action", style="yellow")

        for target, action in sorted(firewall.rules.items())[:20]:
            rules_table.add_row(target[:60], action)

        console.print(rules_table)
    else:
        console.print("[yellow]No rules configured yet[/yellow]")


def interactive_menu():
    """Interactive menu for managing firewall"""
    while True:
        console.print("\n" + "=" * 80)
        console.print("[bold]Network Firewall Management[/bold]")
        console.print("=" * 80)
        console.print("1. View statistics and recent requests")
        console.print("2. View all rules")
        console.print("3. Add rule")
        console.print("4. Remove rule")
        console.print("5. Clear all rules")
        console.print("6. Export rules")
        console.print("0. Exit")

        choice = Prompt.ask("Choose option", choices=["0", "1", "2", "3", "4", "5", "6"])

        if choice == "0":
            break
        elif choice == "1":
            show_stats()
        elif choice == "2":
            for target, action in sorted(firewall.rules.items()):
                console.print(f"[cyan]{target}[/cyan]: [yellow]{action}[/yellow]")
        elif choice == "3":
            target = Prompt.ask("Enter domain or URL")
            action_str = Prompt.ask(
                "Action", choices=["allow", "deny", "allow-domain", "deny-domain"]
            )
            firewall.rules[target] = action_str  # type: ignore[assignment]
            firewall.save_rules()
            console.print("[green]✓ Rule added[/green]")
        elif choice == "4":
            target = Prompt.ask("Enter domain or URL to remove")
            if target in firewall.rules:
                del firewall.rules[target]
                firewall.save_rules()
                console.print("[green]✓ Rule removed[/green]")
            else:
                console.print("[red]Rule not found[/red]")
        elif choice == "5":
            if Confirm.ask("Clear all rules?"):
                firewall.rules.clear()
                firewall.save_rules()
                console.print("[green]✓ All rules cleared[/green]")
        elif choice == "6":
            export_file = Prompt.ask("Export to file", default="network-rules-export.json")
            with open(export_file, "w") as f:
                json.dump(firewall.rules, f, indent=2)
            console.print(f"[green]✓ Exported to {export_file}[/green]")


def addons():
    """Return mitmproxy addons (called by mitmproxy)"""
    return [FirewallAddon()]


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--manage":
            # Interactive management mode
            interactive_menu()
        elif sys.argv[1] == "--stats":
            # Show stats
            show_stats()
        else:
            # Run proxy
            run_proxy()
    else:
        # Default: run proxy
        run_proxy()
