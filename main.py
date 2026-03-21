#!/usr/bin/env python3
import logging
import argparse
import sys
from datetime import time, datetime

from goal_manager import Goal, GoalCategory, GoalManager
from dns_filter import DNSFilter
from screen_time_manager import ScreenTimeManager
from dns_server import DNSServer
from config_manager import ConfigManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SeedHackathon")

class SeedHackathonDNS:
    """Main application for DNS-based parental control"""

    def __init__(self, config_file: str = "config.json"):
        self.config_manager = ConfigManager(config_file)
        self.goal_manager = GoalManager()
        self.screen_time_manager = ScreenTimeManager()
        self.dns_filter = DNSFilter(self.goal_manager, self.screen_time_manager)
        self.dns_server = None

        self._load_from_config()

    def _load_from_config(self) -> None:
        """Load goals and settings from configuration"""
        # Load goals
        for goal in self.config_manager.get_all_goals():
            self.goal_manager.add_goal(goal)

        # Load global blocklist
        for domain in self.config_manager.get_blocklist():
            self.dns_filter.add_global_block(domain)

        logger.info(f"Loaded {len(self.goal_manager.list_all_goals())} goals from config")

    def create_goal(self, goal_id: str, name: str, category: str, domains: list) -> None:
        """Create a new goal"""
        try:
            cat = GoalCategory(category)
            goal = Goal(
                id=goal_id,
                name=name,
                category=cat,
                allowed_domains=set(domains)
            )
            self.goal_manager.add_goal(goal)
            self.config_manager.add_goal(goal)
            logger.info(f"Created goal: {name} ({goal_id})")
        except ValueError:
            logger.error(f"Invalid category: {category}")

    def list_goals(self) -> None:
        """List all goals"""
        goals = self.goal_manager.list_all_goals()
        if not goals:
            print("No goals configured.")
            return

        print("\n=== Goals ===")
        for goal in goals:
            print(f"\nID: {goal.id}")
            print(f"  Name: {goal.name}")
            print(f"  Category: {goal.category.value}")
            print(f"  Status: {'Active' if goal.active else 'Inactive'}")
            print(f"  Domains: {', '.join(goal.allowed_domains) if goal.allowed_domains else 'None'}")

    def test_filter(self, domain: str, device_id: str = "test-device") -> None:
        """Test the DNS filter with a domain"""
        result = self.dns_filter.filter_query(domain, device_id)
        print(f"\nFilter test for: {domain}")
        print(f"  Result: {result.action.value}")
        print(f"  Reason: {result.reason}")

    def add_screen_time_limit(self, device_id: str, daily_limit_minutes: int) -> None:
        """Add screen time limit for a device"""
        self.screen_time_manager.add_device(device_id, daily_limit_minutes)
        logger.info(f"Added screen time limit for {device_id}: {daily_limit_minutes} minutes/day")

    def add_blocklist_domain(self, domain: str) -> None:
        """Add domain to global blocklist"""
        self.dns_filter.add_global_block(domain)
        self.config_manager.add_domain_to_blocklist(domain)
        logger.info(f"Added {domain} to global blocklist")

    def start_server(self) -> None:
        """Start the DNS server"""
        config = self.config_manager.get_dns_server_config()
        port = config.get("listen_port", 5053)
        upstream = config.get("upstream_dns", "8.8.8.8")
        listen_addr = config.get("listen_address", "0.0.0.0")

        self.dns_server = DNSServer(self.dns_filter, port, upstream)

        try:
            logger.info("Starting DNS server...")
            self.dns_server.start(listen_addr)
            logger.info(f"DNS server is running on {listen_addr}:{port}")
            logger.info(f"Upstream DNS: {upstream}")

            # Keep running
            while True:
                pass

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.dns_server.stop()
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            sys.exit(1)

    def show_stats(self) -> None:
        """Show filter statistics"""
        stats = self.dns_filter.get_stats()
        print("\n=== DNS Filter Statistics ===")
        print(f"Total Goals: {stats['total_goals']}")
        print(f"Active Goals: {stats['active_goals']}")
        print(f"Global Blocklist: {stats['global_blocklist_count']} domains")
        print(f"Global Allowlist: {stats['global_allowlist_count']} domains")

def main():
    parser = argparse.ArgumentParser(
        description="SeedHackathon - DNS-based Parental Control System"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Create goal command
    goal_parser = subparsers.add_parser("create-goal", help="Create a new goal")
    goal_parser.add_argument("id", help="Goal ID")
    goal_parser.add_argument("name", help="Goal name")
    goal_parser.add_argument("--category", required=True,
                           choices=["educational", "productivity", "social", "entertainment", "restricted"],
                           help="Goal category")
    goal_parser.add_argument("--domains", nargs="+", default=[], help="Allowed domains")

    # List goals command
    subparsers.add_parser("list-goals", help="List all goals")

    # Test filter command
    test_parser = subparsers.add_parser("test-filter", help="Test DNS filter")
    test_parser.add_argument("domain", help="Domain to test")
    test_parser.add_argument("--device", default="test-device", help="Device ID")

    # Screen time command
    screen_parser = subparsers.add_parser("set-screen-time", help="Set screen time limit")
    screen_parser.add_argument("device_id", help="Device ID")
    screen_parser.add_argument("minutes", type=int, help="Daily limit in minutes")

    # Blocklist command
    block_parser = subparsers.add_parser("block-domain", help="Add domain to blocklist")
    block_parser.add_argument("domain", help="Domain to block")

    # Start server command
    subparsers.add_parser("start-server", help="Start DNS server")

    # Stats command
    subparsers.add_parser("stats", help="Show filter statistics")

    args = parser.parse_args()

    app = SeedHackathonDNS()

    if args.command == "create-goal":
        app.create_goal(args.id, args.name, args.category, args.domains)
    elif args.command == "list-goals":
        app.list_goals()
    elif args.command == "test-filter":
        app.test_filter(args.domain, args.device)
    elif args.command == "set-screen-time":
        app.add_screen_time_limit(args.device_id, args.minutes)
    elif args.command == "block-domain":
        app.add_blocklist_domain(args.domain)
    elif args.command == "start-server":
        app.start_server()
    elif args.command == "stats":
        app.show_stats()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
