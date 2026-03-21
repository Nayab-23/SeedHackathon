from dataclasses import dataclass, field
from typing import List, Set
from enum import Enum
from datetime import time

class GoalCategory(str, Enum):
    """Category of goals for filtering"""
    EDUCATIONAL = "educational"
    PRODUCTIVITY = "productivity"
    ENTERTAINMENT = "entertainment"
    SOCIAL = "social"
    RESTRICTED = "restricted"

@dataclass
class Goal:
    """Represents a daily goal"""
    id: str
    name: str
    category: GoalCategory
    allowed_domains: Set[str] = field(default_factory=set)
    blocked_domains: Set[str] = field(default_factory=set)
    active: bool = True
    created_at: str = ""

@dataclass
class ScreenTimeRule:
    """Screen time restrictions for devices"""
    device_id: str
    daily_limit_minutes: int
    allowed_start_time: time
    allowed_end_time: time
    blocked_domains: Set[str] = field(default_factory=set)

class GoalManager:
    """Manages goals and their associated domains"""

    def __init__(self):
        self.goals: dict[str, Goal] = {}
        self.domain_to_goal: dict[str, str] = {}  # domain -> goal_id mapping

    def add_goal(self, goal: Goal) -> None:
        """Add a new goal"""
        self.goals[goal.id] = goal
        for domain in goal.allowed_domains:
            self.domain_to_goal[domain] = goal.id

    def get_goal(self, goal_id: str) -> Goal | None:
        """Retrieve a goal by ID"""
        return self.goals.get(goal_id)

    def get_goal_for_domain(self, domain: str) -> Goal | None:
        """Find which goal a domain belongs to"""
        goal_id = self.domain_to_goal.get(domain)
        return self.goals.get(goal_id) if goal_id else None

    def add_domain_to_goal(self, goal_id: str, domain: str) -> bool:
        """Add a domain to a goal"""
        if goal_id not in self.goals:
            return False
        self.goals[goal_id].allowed_domains.add(domain)
        self.domain_to_goal[domain] = goal_id
        return True

    def remove_domain_from_goal(self, goal_id: str, domain: str) -> bool:
        """Remove a domain from a goal"""
        if goal_id not in self.goals:
            return False
        self.goals[goal_id].allowed_domains.discard(domain)
        self.domain_to_goal.pop(domain, None)
        return True

    def get_active_goals(self) -> List[Goal]:
        """Get all active goals"""
        return [goal for goal in self.goals.values() if goal.active]

    def list_all_goals(self) -> List[Goal]:
        """List all goals"""
        return list(self.goals.values())
