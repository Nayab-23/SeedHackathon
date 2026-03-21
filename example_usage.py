#!/usr/bin/env python3
"""
Example usage of the SeedHackathon DNS filter system
"""

from goal_manager import Goal, GoalCategory, GoalManager
from dns_filter import DNSFilter, FilterAction
from screen_time_manager import ScreenTimeManager
from datetime import time

def main():
    print("=== SeedHackathon DNS Filter - Example Usage ===\n")

    # Initialize managers
    goal_manager = GoalManager()
    screen_time_manager = ScreenTimeManager()
    dns_filter = DNSFilter(goal_manager, screen_time_manager)

    # Create educational goal
    print("1. Creating educational goal...")
    edu_goal = Goal(
        id="study_morning",
        name="Morning Study Session",
        category=GoalCategory.EDUCATIONAL,
        allowed_domains={
            "wikipedia.org",
            "github.com",
            "stackoverflow.com",
            "python.org",
            "coursera.org"
        }
    )
    goal_manager.add_goal(edu_goal)
    print(f"✓ Created goal: {edu_goal.name}\n")

    # Create productivity goal
    print("2. Creating productivity goal...")
    prod_goal = Goal(
        id="work_afternoon",
        name="Afternoon Work Session",
        category=GoalCategory.PRODUCTIVITY,
        allowed_domains={
            "github.com",
            "slack.com",
            "notion.so",
            "google.com"
        }
    )
    goal_manager.add_goal(prod_goal)
    print(f"✓ Created goal: {prod_goal.name}\n")

    # Set up global blocklist
    print("3. Setting up global blocklist...")
    blocked_sites = ["facebook.com", "tiktok.com", "instagram.com", "twitter.com"]
    for site in blocked_sites:
        dns_filter.add_global_block(site)
    print(f"✓ Blocked {len(blocked_sites)} sites\n")

    # Set up global allowlist (bypass filter)
    print("4. Setting up global allowlist...")
    allowed_sites = ["google.com", "github.com"]
    for site in allowed_sites:
        dns_filter.add_global_allow(site)
    print(f"✓ Allowlisted {len(allowed_sites)} sites\n")

    # Set up screen time
    print("5. Setting up screen time limits...")
    screen_time_manager.add_device("iPhone_john", 120)  # 2 hours/day
    screen_time_manager.add_device("iPad_sarah", 90)    # 1.5 hours/day
    print("✓ Added device screen time limits\n")

    # Test various domains
    print("6. Testing DNS filter...\n")

    test_domains = [
        "github.com",           # In educational goal
        "wikipedia.org",        # In educational goal
        "facebook.com",         # In global blocklist
        "unknown-site.com",     # Unknown
        "docs.github.com",      # Subdomain of allowed
        "reddit.com",           # Unknown
        "google.com",           # In global allowlist
    ]

    for domain in test_domains:
        result = dns_filter.filter_query(domain, "iPhone_john")
        status = "✓ ALLOW" if result.action == FilterAction.ALLOW else \
                 "✗ BLOCK" if result.action == FilterAction.BLOCK else \
                 "⚠ APPROVAL"
        print(f"{status:15} {domain:25} ({result.reason})")

    # Show statistics
    print("\n7. Filter Statistics:")
    stats = dns_filter.get_stats()
    print(f"   Total Goals: {stats['total_goals']}")
    print(f"   Active Goals: {stats['active_goals']}")
    print(f"   Global Blocklist: {stats['global_blocklist_count']} domains")
    print(f"   Global Allowlist: {stats['global_allowlist_count']} domains")

    # Show screen time stats
    print("\n8. Screen Time Statistics:")
    for device_id in ["iPhone_john", "iPad_sarah"]:
        stats = screen_time_manager.get_device_stats(device_id)
        if stats:
            print(f"   {device_id}:")
            print(f"     Daily Limit: {stats['daily_limit_minutes']} min")
            print(f"     Used Today: {stats['usage_today_minutes']} min")
            print(f"     Remaining: {stats['remaining_minutes']} min")

if __name__ == "__main__":
    main()
