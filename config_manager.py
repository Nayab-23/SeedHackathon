import json
from datetime import datetime, time
from pathlib import Path
from typing import Optional, List
from goal_manager import Goal, GoalCategory, GoalManager
import logging

logger = logging.getLogger("ConfigManager")

class ConfigManager:
    """Manages configuration and persistence of goals and rules"""

    def __init__(self, config_file: str = "config.json"):
        self.config_file = Path(config_file)
        self.config = {}
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                logger.info(f"Configuration loaded from {self.config_file}")
            except Exception as e:
                logger.error(f"Error loading configuration: {e}")
                self.config = {}
        else:
            logger.info(f"Configuration file not found, starting with empty config")
            self.create_default_config()

    def save_config(self) -> None:
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2, default=str)
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def create_default_config(self) -> None:
        """Create default configuration"""
        self.config = {
            "goals": [],
            "screen_time_rules": [],
            "global_blocklist": [],
            "global_allowlist": [
                "google.com",
                "github.com",
                "stackoverflow.com",
                "wikipedia.org"
            ],
            "dns_server": {
                "listen_port": 5053,
                "upstream_dns": "8.8.8.8",
                "listen_address": "0.0.0.0"
            }
        }
        self.save_config()

    def add_goal(self, goal: Goal) -> None:
        """Add a goal to configuration"""
        goal_data = {
            "id": goal.id,
            "name": goal.name,
            "category": goal.category.value,
            "allowed_domains": list(goal.allowed_domains),
            "blocked_domains": list(goal.blocked_domains),
            "active": goal.active,
            "created_at": datetime.now().isoformat()
        }
        self.config["goals"].append(goal_data)
        self.save_config()

    def update_goal(self, goal: Goal) -> None:
        """Update an existing goal"""
        for i, g in enumerate(self.config["goals"]):
            if g["id"] == goal.id:
                self.config["goals"][i] = {
                    "id": goal.id,
                    "name": goal.name,
                    "category": goal.category.value,
                    "allowed_domains": list(goal.allowed_domains),
                    "blocked_domains": list(goal.blocked_domains),
                    "active": goal.active,
                    "created_at": g.get("created_at", datetime.now().isoformat())
                }
                self.save_config()
                return

        logger.warning(f"Goal {goal.id} not found")

    def delete_goal(self, goal_id: str) -> None:
        """Delete a goal"""
        self.config["goals"] = [g for g in self.config["goals"] if g["id"] != goal_id]
        self.save_config()

    def get_all_goals(self) -> List[Goal]:
        """Get all goals from configuration"""
        goals = []
        for goal_data in self.config.get("goals", []):
            goal = Goal(
                id=goal_data["id"],
                name=goal_data["name"],
                category=GoalCategory(goal_data["category"]),
                allowed_domains=set(goal_data.get("allowed_domains", [])),
                blocked_domains=set(goal_data.get("blocked_domains", [])),
                active=goal_data.get("active", True),
                created_at=goal_data.get("created_at", "")
            )
            goals.append(goal)
        return goals

    def add_domain_to_blocklist(self, domain: str) -> None:
        """Add domain to global blocklist"""
        if domain not in self.config["global_blocklist"]:
            self.config["global_blocklist"].append(domain)
            self.save_config()

    def remove_domain_from_blocklist(self, domain: str) -> None:
        """Remove domain from global blocklist"""
        self.config["global_blocklist"] = [
            d for d in self.config["global_blocklist"] if d != domain
        ]
        self.save_config()

    def get_blocklist(self) -> List[str]:
        """Get global blocklist"""
        return self.config.get("global_blocklist", [])

    def get_dns_server_config(self) -> dict:
        """Get DNS server configuration"""
        return self.config.get("dns_server", {
            "listen_port": 5053,
            "upstream_dns": "8.8.8.8",
            "listen_address": "0.0.0.0"
        })

    def set_dns_server_config(self, config: dict) -> None:
        """Update DNS server configuration"""
        self.config["dns_server"] = config
        self.save_config()
