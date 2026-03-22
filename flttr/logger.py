"""
FLTTR Logger — rich-powered colored logging for the whole system.

Usage:
    from flttr.logger import log

    log.dns("ALLOWED", "google.com", "A", "192.168.1.5", 12.3)
    log.dns("BLOCKED", "tiktok.com", "A", "192.168.1.5", 1.2)
    log.api("POST /api/lists", "added tiktok.com to blacklist")
    log.agent("block", ["tiktok.com", "instagram.com"])
    log.system("Database initialized")
    log.error("Upstream DNS timeout")
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from datetime import datetime

console = Console()

ACTION_STYLES = {
    "ALLOWED": "green",
    "BLOCKED": "bold red",
    "ERROR": "bold yellow",
}


class FlttrLogger:
    def banner(self):
        banner_text = Text()
        banner_text.append("  _____ _   _____ ___\n", style="bold cyan")
        banner_text.append(" |  ___| | |_   _| _ \\\n", style="bold cyan")
        banner_text.append(" | |_  | |   | | |   /\n", style="bold cyan")
        banner_text.append(" |  _| | |__ | | | |\\ \\\n", style="bold cyan")
        banner_text.append(" |_|   |____||_| |_| \\_\\\n", style="bold cyan")
        banner_text.append("\n AI-Powered DNS Filtering", style="dim")
        console.print(Panel(banner_text, border_style="cyan", padding=(0, 2)))

    def system(self, message: str):
        ts = self._timestamp()
        console.print(f"[dim]{ts}[/dim] [bold cyan]SYS[/bold cyan]    {message}")

    def dns(self, action: str, domain: str, qtype: str, client_ip: str, ms: float):
        ts = self._timestamp()
        style = ACTION_STYLES.get(action, "white")
        action_str = f"[{style}]{action:<7}[/{style}]"
        console.print(
            f"[dim]{ts}[/dim] [bold blue]DNS[/bold blue]    {action_str} {qtype:<5} [bold]{domain:<40}[/bold] [dim]from[/dim] {client_ip:<15} [dim]{ms:.1f}ms[/dim]"
        )

    def api(self, method_path: str, detail: str = ""):
        ts = self._timestamp()
        msg = f"[dim]{ts}[/dim] [bold magenta]API[/bold magenta]    {method_path}"
        if detail:
            msg += f" [dim]— {detail}[/dim]"
        console.print(msg)

    def agent(self, action: str, domains: list = None, detail: str = ""):
        ts = self._timestamp()
        if domains:
            domain_str = ", ".join(domains)
            console.print(
                f"[dim]{ts}[/dim] [bold yellow]AGENT[/bold yellow]  {action} [bold]{domain_str}[/bold]"
            )
        elif detail:
            console.print(
                f"[dim]{ts}[/dim] [bold yellow]AGENT[/bold yellow]  {action} [dim]— {detail}[/dim]"
            )
        else:
            console.print(f"[dim]{ts}[/dim] [bold yellow]AGENT[/bold yellow]  {action}")

    def error(self, message: str):
        ts = self._timestamp()
        console.print(f"[dim]{ts}[/dim] [bold red]ERR[/bold red]    {message}")

    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S")


log = FlttrLogger()
