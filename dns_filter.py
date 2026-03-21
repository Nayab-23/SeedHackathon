from typing import Optional, Set
from datetime import datetime, time
from enum import Enum
import socket

class FilterAction(str, Enum):
    """Action to take on a DNS query"""
    ALLOW = "allow"
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"

class FilterResult:
    """Result of a DNS filter check"""
    def __init__(self, action: FilterAction, reason: str = ""):
        self.action = action
        self.reason = reason
        self.timestamp = datetime.now()

    def __repr__(self):
        return f"FilterResult(action={self.action}, reason={self.reason})"

class DNSFilter:
    """Core DNS filtering engine"""

    def __init__(self, goal_manager, screen_time_manager=None):
        self.goal_manager = goal_manager
        self.screen_time_manager = screen_time_manager
        self.global_blocklist: Set[str] = set()
        self.global_allowlist: Set[str] = set()

    def add_global_block(self, domain: str) -> None:
        """Add domain to global blocklist"""
        self.global_blocklist.add(self._normalize_domain(domain))

    def add_global_allow(self, domain: str) -> None:
        """Add domain to global allowlist"""
        self.global_allowlist.add(self._normalize_domain(domain))

    def remove_global_block(self, domain: str) -> None:
        """Remove domain from global blocklist"""
        self.global_blocklist.discard(self._normalize_domain(domain))

    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain for comparison"""
        return domain.lower().strip()

    def _is_subdomain_match(self, query_domain: str, rule_domain: str) -> bool:
        """Check if query domain matches rule domain or its subdomains"""
        query = self._normalize_domain(query_domain)
        rule = self._normalize_domain(rule_domain)

        if query == rule:
            return True

        # Check if query is a subdomain of rule
        if query.endswith("." + rule):
            return True

        return False

    def filter_query(self, domain: str, device_id: str = "default") -> FilterResult:
        """
        Filter a DNS query

        Args:
            domain: Domain being queried
            device_id: ID of the device making the query

        Returns:
            FilterResult with action and reason
        """
        normalized_domain = self._normalize_domain(domain)

        # Check global blocklist
        for blocked in self.global_blocklist:
            if self._is_subdomain_match(normalized_domain, blocked):
                return FilterResult(
                    FilterAction.BLOCK,
                    f"Domain in global blocklist: {blocked}"
                )

        # Check global allowlist (allowlist overrides other rules)
        for allowed in self.global_allowlist:
            if self._is_subdomain_match(normalized_domain, allowed):
                return FilterResult(
                    FilterAction.ALLOW,
                    f"Domain in global allowlist: {allowed}"
                )

        # Check screen time restrictions
        if self.screen_time_manager:
            screen_time_result = self.screen_time_manager.check_device(
                device_id, normalized_domain
            )
            if screen_time_result.action == FilterAction.BLOCK:
                return screen_time_result

        # Check goals
        goal = self.goal_manager.get_goal_for_domain(normalized_domain)
        if goal and goal.active:
            return FilterResult(FilterAction.ALLOW, f"Matches goal: {goal.name}")

        # Check if domain is in any active goal's allowed list
        for goal in self.goal_manager.get_active_goals():
            for allowed_domain in goal.allowed_domains:
                if self._is_subdomain_match(normalized_domain, allowed_domain):
                    return FilterResult(
                        FilterAction.ALLOW,
                        f"Allowed by goal: {goal.name}"
                    )

        # Default: require approval for unknown domains
        return FilterResult(
            FilterAction.REQUIRE_APPROVAL,
            "Domain not in any active goal - requires approval"
        )

    def get_stats(self) -> dict:
        """Get filter statistics"""
        return {
            "global_blocklist_count": len(self.global_blocklist),
            "global_allowlist_count": len(self.global_allowlist),
            "total_goals": len(self.goal_manager.list_all_goals()),
            "active_goals": len(self.goal_manager.get_active_goals()),
        }
