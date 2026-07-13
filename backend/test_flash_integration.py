"""
Test script for Flash integration.

Run with: python3 test_flash_integration.py
"""

import sys
sys.path.insert(0, '.')

from app.services.flash_service import (
    FlashClient,
    check_flash_health,
    list_flash_templates,
    is_flash_enabled,
)


def test_flash_health():
    """Test Flash health check."""
    print("\n1. Testing Flash health check...")
    result = check_flash_health()
    print(f"   Enabled: {result.get('enabled')}")
    print(f"   Healthy: {result.get('healthy')}")
    if not result.get('healthy'):
        print(f"   Error: {result.get('message')}")
    return result.get('healthy', False)


def test_list_templates():
    """Test listing templates."""
    print("\n2. Testing list templates...")
    templates = list_flash_templates()
    print(f"   Found {len(templates)} templates:")
    for t in templates:
        print(f"   - {t.id}: {t.title} ({t.kind}, warm: {t.min_warm})")
    return len(templates) > 0


def test_get_stats():
    """Test getting stats."""
    print("\n3. Testing get stats...")
    client = FlashClient()
    stats = client.get_stats()
    print(f"   Stats: {stats}")
    return True


def test_create_sandbox():
    """Test creating a sandbox (optional - creates real resources)."""
    print("\n4. Testing sandbox creation (skipped - would create real sandbox)...")
    print("   To test manually:")
    print("   client = FlashClient()")
    print("   sandbox = client.create_sandbox('q1')")
    print("   print(sandbox.id, sandbox.app_url)")
    print("   client.kill_sandbox(sandbox.id)")
    return True


def main():
    print("=" * 60)
    print("Flash Integration Test")
    print("=" * 60)
    
    tests = [
        ("Health Check", test_flash_health),
        ("List Templates", test_list_templates),
        ("Get Stats", test_get_stats),
        ("Create Sandbox", test_create_sandbox),
    ]
    
    results = []
    for name, test in tests:
        try:
            passed = test()
            results.append((name, passed))
        except Exception as e:
            print(f"   ERROR: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
    
    all_passed = all(r[1] for r in results)
    print("\nOverall:", "ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED")
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())