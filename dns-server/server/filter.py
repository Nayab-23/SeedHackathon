from enum import Enum
from typing import Set


class Action(Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"


class DomainFilter:
    def __init__(self, blacklist_path: str):
        self.blacklist_path = blacklist_path
        self.blacklist: Set[str] = set()
        self._load_list()

    def _normalize_domain(self, domain: str) -> str:
        domain = domain.strip().lower()
        if domain.endswith("."):
            domain = domain[:-1]
        return domain

    def _load_list(self):
        domains = set()
        try:
            with open(self.blacklist_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    domain = self._normalize_domain(line)
                    if domain:
                        domains.add(domain)
        except FileNotFoundError:
            pass
        self.blacklist = domains

    def reload(self):
        self._load_list()

    def _is_subdomain_of(self, domain: str, target: str) -> bool:
        if domain == target:
            return True
        if domain.endswith("." + target):
            return True
        return False

    def check(self, domain: str) -> Action:
        domain = self._normalize_domain(domain)
        for entry in self.blacklist:
            if self._is_subdomain_of(domain, entry):
                return Action.BLOCKED
        return Action.ALLOWED
