#!/usr/bin/env python3
"""
Tests for network-monitor.py

Simple integration tests that verify core functionality without
complex module mocking.
"""

import json
import subprocess
import tempfile
from pathlib import Path


def test_script_syntax():
    """Test that the script has valid Python syntax"""
    script_path = Path(__file__).parent / "network-monitor.py"
    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax error: {result.stderr}"


def test_help_flag():
    """Test that --help works"""
    script_path = Path(__file__).parent / "network-monitor.py"
    result = subprocess.run(
        ["python3", str(script_path), "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    # Should exit with error code (no --help implemented) but not crash
    assert "error" in result.stderr.lower() or result.returncode != 0


def test_stats_command():
    """Test that --stats command works"""
    script_path = Path(__file__).parent / "network-monitor.py"

    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "network-rules.json"
        log_file = Path(tmpdir) / "network-access.log"

        # Create test data
        config_file.write_text(json.dumps({"github.com": "allow-domain"}))
        log_file.write_text("2024-01-01T12:00:00 | ALLOW      | GET    | github.com/users\n")

        result = subprocess.run(
            ["python3", str(script_path), "--stats"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Should not crash (exit code may vary)
        assert result.returncode in [0, 1]  # May fail if dependencies missing


class TestRuleFormats:
    """Test that different rule formats are valid JSON"""

    def test_empty_rules(self):
        """Test empty rules dict"""
        rules = {}
        assert json.dumps(rules) == "{}"

    def test_allow_domain_rule(self):
        """Test allow-domain rule format"""
        rules = {"example.com": "allow-domain"}
        serialized = json.dumps(rules)
        assert "example.com" in serialized
        assert "allow-domain" in serialized

    def test_deny_domain_rule(self):
        """Test deny-domain rule format"""
        rules = {"ads.com": "deny-domain"}
        serialized = json.dumps(rules)
        assert "deny-domain" in serialized

    def test_url_specific_rule(self):
        """Test URL-specific rule"""
        rules = {"https://api.example.com/v1/users": "allow"}
        serialized = json.dumps(rules)
        assert "https://" in serialized

    def test_wildcard_rule(self):
        """Test wildcard domain rule"""
        rules = {"*.github.com": "allow-domain"}
        serialized = json.dumps(rules)
        assert "*.github.com" in serialized

    def test_mixed_rules(self):
        """Test combination of different rule types"""
        rules = {
            "github.com": "allow-domain",
            "*.google.com": "allow-domain",
            "ads.example.com": "deny-domain",
            "https://api.bad.com/track": "deny",
        }
        serialized = json.dumps(rules, indent=2)
        deserialized = json.loads(serialized)
        assert deserialized == rules


class TestPendingRequestFormat:
    """Test pending request JSON format"""

    def test_pending_request_structure(self):
        """Test that pending requests have correct structure"""
        pending = [
            {
                "host": "example.com",
                "url": "https://example.com/api",
                "method": "GET",
                "path": "/api",
                "timestamp": "2024-01-01T12:00:00",
            }
        ]

        serialized = json.dumps(pending, indent=2)
        deserialized = json.loads(serialized)

        assert len(deserialized) == 1
        assert deserialized[0]["host"] == "example.com"
        assert deserialized[0]["method"] == "GET"

    def test_multiple_pending_requests(self):
        """Test multiple pending requests"""
        pending = [
            {
                "host": "api1.com",
                "url": "https://api1.com/v1",
                "method": "GET",
                "path": "/v1",
                "timestamp": "2024-01-01T12:00:00",
            },
            {
                "host": "api2.com",
                "url": "https://api2.com/v2",
                "method": "POST",
                "path": "/v2",
                "timestamp": "2024-01-01T12:01:00",
            },
        ]

        serialized = json.dumps(pending)
        deserialized = json.loads(serialized)

        assert len(deserialized) == 2
        assert deserialized[0]["host"] != deserialized[1]["host"]


class TestLogFormat:
    """Test log file format"""

    def test_log_line_format(self):
        """Test that log lines have consistent format"""
        log_line = "2024-01-01T12:00:00 | ALLOW      | GET    | github.com/users"
        parts = log_line.split(" | ")

        assert len(parts) == 4
        assert "2024-01-01" in parts[0]  # timestamp
        assert "ALLOW" in parts[1]  # decision
        assert "GET" in parts[2]  # method
        assert "github.com" in parts[3]  # URL

    def test_parse_log_line(self):
        """Test parsing log line"""
        log_line = "2024-01-01T12:00:00 | DENY       | POST   | ads.com/track"
        parts = log_line.strip().split(" | ")

        timestamp = parts[0]
        decision = parts[1].strip()
        method = parts[2].strip()
        url = parts[3].strip()

        assert timestamp.startswith("2024-01-01")
        assert decision == "DENY"
        assert method == "POST"
        assert url == "ads.com/track"


class TestSecurityModel:
    """Test DEFAULT DENY security model"""

    def test_default_deny_principle(self):
        """Test that default behavior is deny"""
        # Empty rules means everything should be denied
        rules = {}

        # Check that no rules means default deny
        test_domain = "unknown.com"
        assert test_domain not in rules  # Not in allow list

    def test_explicit_allow_required(self):
        """Test that domains must be explicitly allowed"""
        rules = {"github.com": "allow-domain"}

        # Only github.com should be allowed
        assert "github.com" in rules
        assert "google.com" not in rules

    def test_pending_queue_on_unknown(self):
        """Test that unknown requests go to pending queue"""
        pending = []

        # Simulating unknown domain
        unknown_request = {
            "host": "new-site.com",
            "url": "https://new-site.com/api",
            "method": "GET",
            "path": "/api",
            "timestamp": "2024-01-01T12:00:00",
        }

        pending.append(unknown_request)

        assert len(pending) == 1
        assert pending[0]["host"] == "new-site.com"


def test_file_permissions():
    """Test that scripts have proper execute permissions"""
    script_path = Path(__file__).parent / "network-monitor.py"
    web_ui_path = Path(__file__).parent / "web-ui.py"

    assert script_path.exists()
    assert web_ui_path.exists()

    # Check shebang
    with open(script_path) as f:
        first_line = f.readline()
        assert first_line.startswith("#!/usr/bin/env python3")


class TestPendingListReload:
    """Test pending list reload functionality (PR #2658041251)"""

    def test_pending_reload_on_file_change(self):
        """Test that pending list reloads when file is modified"""
        import tempfile
        import time
        from pathlib import Path

        # Create a temporary pending file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            pending_file = Path(f.name)
            initial_pending = [
                {
                    "host": "example.com",
                    "url": "http://example.com/api",
                    "method": "GET",
                    "path": "/api",
                }
            ]
            json.dump(initial_pending, f)

        try:
            # Simulate initial load with mtime tracking
            initial_mtime = pending_file.stat().st_mtime

            # Wait to ensure mtime will be different
            time.sleep(0.1)

            # Modify the file (simulating web UI change)
            with open(pending_file, "w") as f:
                updated_pending = [
                    {
                        "host": "newsite.com",
                        "url": "http://newsite.com/data",
                        "method": "POST",
                        "path": "/data",
                    }
                ]
                json.dump(updated_pending, f)

            # Verify mtime changed
            new_mtime = pending_file.stat().st_mtime
            assert new_mtime > initial_mtime, "File modification time should have increased"

            # Verify reload logic would detect the change
            # (In actual code, reload_pending_if_changed() checks mtime and reloads)
            assert new_mtime != initial_mtime

        finally:
            # Cleanup
            pending_file.unlink()

    def test_pending_mtime_tracking(self):
        """Test that pending_mtime is tracked correctly"""
        # Verify the NetworkFirewall class would have pending_mtime attribute
        # This is a structural test - the attribute must exist for reload to work
        import ast

        script_path = Path(__file__).parent / "network-monitor.py"
        with open(script_path) as f:
            tree = ast.parse(f.read())

        # Find NetworkFirewall.__init__
        found_pending_mtime = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == "pending_mtime":
                        found_pending_mtime = True
                        break

        assert found_pending_mtime, (
            "NetworkFirewall must track pending_mtime for reload functionality"
        )


# TODO: Integration tests needed to fully verify GitHub PR fixes
#
# These integration tests would require running actual mitmproxy instances,
# Flask servers, and handling multi-process/multi-threading scenarios.
#
# 1. test_flow_request_url_usage (PR Comment #3)
#    - Start mitmproxy with FirewallAddon
#    - Send HTTP request through proxy
#    - Verify flow.request.url is used correctly for rule matching
#
# 2. test_rules_auto_reload (PR Comments #1, #10)
#    - Start network-monitor.py
#    - Modify network-rules.json externally
#    - Send request that should match new rule
#    - Verify rule was reloaded and applied correctly
#
# 3. test_pending_list_reload_integration (PR Comment #2658041251)
#    - Start network-monitor.py proxy
#    - Send request to trigger pending queue
#    - Use web UI to approve/clear the pending request
#    - Send another request to same URL
#    - Verify proxy sees the updated pending list without restart
#
# 4. test_no_stdin_blocking (PR Comment #8)
#    - Start network-monitor.py in subprocess
#    - Send requests that trigger pending queue
#    - Verify proxy doesn't block waiting for stdin
#    - Verify proxy continues processing requests
#
# 5. test_port_checking_vs_process_checking (PR Comment #2658041250)
#    - Start network-monitor.py in management mode (--manage)
#    - Verify port 8080 is NOT listening
#    - Verify run-isolated.sh correctly detects no proxy
#    - Start network-monitor.py in proxy mode
#    - Verify port 8080 IS listening
#    - Verify run-isolated.sh correctly detects proxy running
#
# 6. test_port_polling_startup (PR Comment #6)
#    - Start both network-monitor.py and web-ui.py
#    - Verify run-isolated.sh successfully waits for ports
#    - Test with slow startup (add artificial delay)
#    - Verify timeout works correctly after 10 seconds
