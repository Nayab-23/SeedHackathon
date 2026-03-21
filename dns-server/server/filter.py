from typing import Set
from openclaw.observer import Action


class DomainFilter:
    def __init__(self, blacklist_path: str, whitelist_path: str):
        self.blacklist_path = blacklist_path
        self.whitelist_path = whitelist_path
        self.blacklist: Set[str] = set()
        self.whitelist: Set[str] = set()
        self._load_lists()

    def _normalize_domain(self, domain: str) -> str:
        domain = domain.strip().lower()
        if domain.endswith("."):
            domain = domain[:-1]
        return domain

    def _load_list(self, filepath: str) -> Set[str]:
        domains = set()
        try:
            with open(filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    domain = self._normalize_domain(line)
                    if domain:
                        domains.add(domain)
        except FileNotFoundError:
            pass
        return domains

    def _load_lists(self):
        self.blacklist = self._load_list(self.blacklist_path)
        self.whitelist = self._load_list(self.whitelist_path)

    def reload(self):
        self._load_lists()

    def _is_subdomain_of(self, domain: str, target: str) -> bool:
        if domain == target:
            return True
        if domain.endswith("." + target):
            return True
        return False

    def _check_in_list(self, domain: str, domain_list: Set[str]) -> bool:
        for entry in domain_list:
            if self._is_subdomain_of(domain, entry):
                return True
        return False

    def check(self, domain: str) -> Action:
        domain = self._normalize_domain(domain)

        if self._check_in_list(domain, self.whitelist):
            return Action.WHITELISTED

        if self._check_in_list(domain, self.blacklist):
            return Action.BLOCKED

        return Action.ALLOWED
