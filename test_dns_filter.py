#!/usr/bin/env python3
"""
Test suite for DNS filter system
"""

import sys
from goal_manager import Goal, GoalCategory, GoalManager
from dns_filter import DNSFilter, FilterAction
from screen_time_manager import ScreenTimeManager
from datetime import time

def test_goal_management():
    """Test goal creation and management"""
    print("=== Testing Goal Management ===")

    goal_manager = GoalManager()

    # Create educational goal
    edu_goal = Goal(
        id="goal_1",
        name="Morning Study Session",
        category=GoalCategory.EDUCATIONAL,
        allowed_domains={"wikipedia.org", "github.com", "stackoverflow.com", "python.org"}
    )

    goal_manager.add_goal(edu_goal)

    # Verify goal was added
    assert goal_manager.get_goal("goal_1") == edu_goal
    print("✓ Goal created and retrieved successfully")

    # Test domain-to-goal mapping
    goal = goal_manager.get_goal_for_domain("github.com")
    assert goal is not None and goal.id == "goal_1"
    print("✓ Domain-to-goal mapping works")

def test_dns_filter():
    """Test DNS filtering logic"""
    print("\n=== Testing DNS Filter ===")

    goal_manager = GoalManager()
    screen_time_manager = ScreenTimeManager()
    dns_filter = DNSFilter(goal_manager, screen_time_manager)

    # Create and add educational goal
    edu_goal = Goal(
        id="goal_edu",
        name="Study",
        category=GoalCategory.EDUCATIONAL,
        allowed_domains={"wikipedia.org", "github.com"}
    )
    goal_manager.add_goal(edu_goal)

    # Test 1: Allowed domain from goal
    result = dns_filter.filter_query("github.com", "device_1")
    assert result.action == FilterAction.ALLOW
    print("✓ Allowed domain from goal passes filter")

    # Test 2: Unknown domain requires approval
    result = dns_filter.filter_query("unknown-site.com", "device_1")
    assert result.action == FilterAction.REQUIRE_APPROVAL
    print("✓ Unknown domain requires approval")

    # Test 3: Global blocklist
    dns_filter.add_global_block("facebook.com")
    result = dns_filter.filter_query("facebook.com", "device_1")
    assert result.action == FilterAction.BLOCK
    print("✓ Global blocklist blocks domains")

    # Test 4: Subdomain matching
    result = dns_filter.filter_query("docs.github.com", "device_1")
    assert result.action == FilterAction.ALLOW
    print("✓ Subdomain matching works")

    # Test 5: Global allowlist overrides
    dns_filter.add_global_allow("educational-site.com")
    result = dns_filter.filter_query("educational-site.com", "device_1")
    assert result.action == FilterAction.ALLOW
    print("✓ Global allowlist works")

def test_screen_time():
    """Test screen time management"""
    print("\n=== Testing Screen Time Management ===")

    screen_time_manager = ScreenTimeManager()

    # Add device with 60 minute daily limit
    screen_time_manager.add_device("phone_1", 60)

    # Check device can access
    result = screen_time_manager.check_device("phone_1")
    assert result.action == FilterAction.ALLOW
    print("✓ Device within screen time limit")

    # Test time restrictions
    screen_time_manager.set_time_restriction(
        "phone_1",
        time(9, 0),
        time(17, 0),
        allowed=True
    )

    result = screen_time_manager.check_device("phone_1")
    # The result depends on current time, but shouldn't error
    print(f"✓ Time restrictions configured: {result.action}")

    # Get stats
    stats = screen_time_manager.get_device_stats("phone_1")
    assert stats is not None
    assert stats["daily_limit_minutes"] == 60
    print("✓ Device statistics work")

def test_config_persistence():
    """Test configuration saving and loading"""
    print("\n=== Testing Configuration Persistence ===")

    from config_manager import ConfigManager
    import os

    test_config = "test_config.json"

    try:
        # Create config with a goal
        config_manager = ConfigManager(test_config)

        goal = Goal(
            id="test_goal",
            name="Test Goal",
            category=GoalCategory.EDUCATIONAL,
            allowed_domains={"test.com"}
        )

        config_manager.add_goal(goal)

        # Load it back
        config_manager2 = ConfigManager(test_config)
        goals = config_manager2.get_all_goals()

        assert len(goals) == 1
        assert goals[0].id == "test_goal"
        print("✓ Configuration persistence works")

    finally:
        # Cleanup
        if os.path.exists(test_config):
            os.remove(test_config)

def run_all_tests():
    """Run all tests"""
    try:
        test_goal_management()
        test_dns_filter()
        test_screen_time()
        test_config_persistence()

        print("\n" + "="*50)
        print("✓ All tests passed!")
        print("="*50)
        return 0

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
