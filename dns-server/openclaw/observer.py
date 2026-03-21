from enum import Enum
from datetime import datetime
import logging
import os
from colorama import init, Fore, Style

init(autoreset=True)


class Action(Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    WHITELISTED = "WHITELISTED"
    ERROR = "ERROR"


class OpenClaw:
    def __init__(self, enabled=True, log_file="logs/openclaw.log"):
        self.enabled = enabled
        self.log_file = log_file
        self.total_queries = 0
        self.blocked_count = 0
        self.allowed_count = 0
        self.whitelisted_count = 0
        self.error_count = 0

        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        self.logger = logging.getLogger("openclaw")
        self.logger.setLevel(logging.INFO)

        if not self.logger.handlers:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(file_handler)

    def startup_banner(self):
        banner = """
    ____                   ___________       __
   / __ \____  ___  ____  / ____/ ___/__  _/ /
  / / / / __ \/ _ \/ __ \/ /    \__ \/ / / / / 
 / /_/ / /_/ /  __/ / / / /___ ___/ / /_/ / /  
/_____/\____/\___/_/ /_/\____//____/\__,_/_/   
                                               
        DNS Observer - Watching All Traffic
        """
        print(Fore.CYAN + banner + Style.RESET_ALL)
        print(Fore.GREEN + f"[+] Logging to: {self.log_file}" + Style.RESET_ALL)
        print(Fore.GREEN + "[+] OpenClaw observer active\n" + Style.RESET_ALL)

    def observe(self, client_ip, domain, query_type, action, response_ms, extra=None):
        if not self.enabled:
            return

        self.total_queries += 1

        if action == Action.BLOCKED:
            self.blocked_count += 1
            color = Fore.RED
        elif action == Action.ALLOWED:
            self.allowed_count += 1
            color = Fore.GREEN
        elif action == Action.WHITELISTED:
            self.whitelisted_count += 1
            color = Fore.CYAN
        else:
            self.error_count += 1
            color = Fore.YELLOW

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        action_str = f"[{action.value:^11}]"

        log_line = f"[{timestamp}] {action_str} {query_type:<6} {domain:<40} from {client_ip:<15} {response_ms:.1f}ms"

        print(color + log_line + Style.RESET_ALL)

        plain_log_line = f"[{timestamp}] {action_str} {query_type:<6} {domain:<40} from {client_ip:<15} {response_ms:.1f}ms"
        self.logger.info(plain_log_line)

    def print_stats(self):
        print(Fore.CYAN + "\n" + "=" * 60 + Style.RESET_ALL)
        print(Fore.CYAN + "OpenClaw Session Summary" + Style.RESET_ALL)
        print(Fore.CYAN + "=" * 60 + Style.RESET_ALL)
        print(f"Total queries:    {self.total_queries}")
        print(Fore.GREEN + f"Allowed:          {self.allowed_count}" + Style.RESET_ALL)
        print(
            Fore.CYAN + f"Whitelisted:      {self.whitelisted_count}" + Style.RESET_ALL
        )
        print(Fore.RED + f"Blocked:          {self.blocked_count}" + Style.RESET_ALL)
        print(Fore.YELLOW + f"Errors:           {self.error_count}" + Style.RESET_ALL)
        print(Fore.CYAN + "=" * 60 + Style.RESET_ALL)
