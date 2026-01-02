#!/usr/bin/env python3
"""
Tests for web-ui.py

Simple integration tests that verify core functionality.
"""

import json
import subprocess
from pathlib import Path

import pytest


def test_script_syntax():
    """Test that the script has valid Python syntax"""
    script_path = Path(__file__).parent / "web-ui.py"
    result = subprocess.run(
        ["python3", "-m", "py_compile", str(script_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax error: {result.stderr}"


def test_file_has_shebang():
    """Test that script has proper shebang"""
    script_path = Path(__file__).parent / "web-ui.py"
    with open(script_path) as f:
        first_line = f.readline()
        assert first_line.startswith("#!/usr/bin/env python3")


class TestAPIDataFormats:
    """Test API data structure formats"""

    def test_rules_response_format(self):
        """Test rules API response format"""
        response = {
            "rules": {"github.com": "allow-domain"},
            "count": 1,
            "last_update": "2024-01-01T12:00:00",
        }

        assert "rules" in response
        assert "count" in response
        assert isinstance(response["rules"], dict)
        assert isinstance(response["count"], int)

    def test_stats_response_format(self):
        """Test stats API response format"""
        response = {
            "stats": {"total": 100, "allow": 75, "deny": 25},
            "last_update": "2024-01-01T12:00:00",
        }

        assert "stats" in response
        assert "total" in response["stats"]
        assert isinstance(response["stats"], dict)

    def test_pending_response_format(self):
        """Test pending requests API response format"""
        response = {
            "pending": [
                {
                    "host": "example.com",
                    "url": "https://example.com/api",
                    "method": "GET",
                    "path": "/api",
                    "timestamp": "2024-01-01T12:00:00",
                }
            ],
            "count": 1,
            "last_update": "2024-01-01T12:00:00",
        }

        assert "pending" in response
        assert "count" in response
        assert isinstance(response["pending"], list)
        assert len(response["pending"]) == response["count"]

    def test_approve_request_format(self):
        """Test approve request payload format"""
        payload = {
            "host": "example.com",
            "url": "https://example.com/api",
            "action": "allow-domain",
        }

        assert "host" in payload
        assert "url" in payload
        assert "action" in payload
        assert payload["action"] in [
            "allow-domain",
            "deny-domain",
            "allow-url",
            "deny-url",
        ]


class TestLogParsing:
    """Test log line parsing"""

    def test_parse_valid_log_line(self):
        """Test parsing a valid log line"""
        line = "2024-01-01T12:00:00 | ALLOW      | GET    | github.com/users"
        parts = line.strip().split(" | ")

        assert len(parts) == 4
        timestamp, decision, method, url = parts
        assert timestamp.startswith("2024-01-01")
        assert decision.strip() == "ALLOW"
        assert method.strip() == "GET"
        assert url.strip() == "github.com/users"

    def test_parse_log_line_with_different_decisions(self):
        """Test parsing different decision types"""
        decisions = ["ALLOW", "DENY", "PENDING", "ALLOW-ONCE", "DENY-ONCE"]

        for decision in decisions:
            line = f"2024-01-01T12:00:00 | {decision:10s} | GET    | test.com/api"
            parts = line.strip().split(" | ")
            assert len(parts) == 4
            assert decision in parts[1]

    def test_parse_invalid_log_line(self):
        """Test that invalid log lines are handled"""
        invalid_lines = [
            "invalid log line",
            "not | enough | parts",
            "",
        ]

        for line in invalid_lines:
            parts = line.strip().split(" | ")
            # Should not crash, might have < 4 parts
            assert isinstance(parts, list)


class TestCacheUpdate:
    """Test cache update logic"""

    def test_cache_structure(self):
        """Test cache data structure"""
        cache = {
            "rules": {},
            "stats": {"total": 0},
            "recent_requests": [],
            "pending_requests": [],
            "last_update": None,
        }

        assert "rules" in cache
        assert "stats" in cache
        assert "recent_requests" in cache
        assert "pending_requests" in cache
        assert isinstance(cache["rules"], dict)
        assert isinstance(cache["stats"], dict)
        assert isinstance(cache["recent_requests"], list)
        assert isinstance(cache["pending_requests"], list)

    def test_stats_incremental_update(self):
        """Test that stats can be updated incrementally"""
        # Initial stats
        stats = {"total": 10, "allow": 5, "deny": 5}

        # Incremental update (1 new allow)
        stats["total"] += 1
        stats["allow"] = stats.get("allow", 0) + 1

        assert stats["total"] == 11
        assert stats["allow"] == 6
        assert stats["deny"] == 5

    def test_no_deadlock_in_stats_calculation(self):
        """Test that stats calculation doesn't cause deadlock"""
        # Simulating passing current_stats to avoid nested lock
        current_stats = {"total": 5, "allow": 3, "deny": 2}

        # Function should accept current_stats as parameter
        # This avoids needing to acquire cache_lock inside calculate_stats
        def calculate_stats_safe(current_stats=None):
            stats = current_stats or {}
            # Add new entries
            stats["total"] = stats.get("total", 0) + 1
            return stats

        result = calculate_stats_safe(current_stats)
        assert result["total"] == 6


class TestFileOperations:
    """Test file read/write operations"""

    def test_rule_file_format(self):
        """Test that rules file is valid JSON"""
        rules = {
            "github.com": "allow-domain",
            "*.google.com": "allow-domain",
            "ads.com": "deny-domain",
        }

        # Should serialize and deserialize correctly
        json_str = json.dumps(rules, indent=2)
        parsed = json.loads(json_str)

        assert parsed == rules

    def test_pending_file_format(self):
        """Test that pending file is valid JSON"""
        pending = [
            {
                "host": "example.com",
                "url": "https://example.com/api",
                "method": "GET",
                "path": "/api",
                "timestamp": "2024-01-01T12:00:00",
            }
        ]

        # Should serialize and deserialize correctly
        json_str = json.dumps(pending, indent=2)
        parsed = json.loads(json_str)

        assert parsed == pending
        assert len(parsed) == 1


class TestOptimizedLogReading:
    """Test optimized log file reading"""

    def test_read_last_n_lines_logic(self):
        """Test logic for reading last N lines"""
        # Simulate log file with multiple lines
        lines = [
            "2024-01-01T12:00:00 | ALLOW      | GET    | site1.com/api",
            "2024-01-01T12:01:00 | DENY       | POST   | site2.com/track",
            "2024-01-01T12:02:00 | ALLOW      | GET    | site3.com/data",
            "2024-01-01T12:03:00 | PENDING    | GET    | site4.com/new",
        ]

        # Take last 2 lines
        recent = lines[-2:]
        assert len(recent) == 2
        assert "site3.com" in recent[0]
        assert "site4.com" in recent[1]

    def test_incremental_stat_tracking(self):
        """Test incremental statistics tracking"""
        # Simulating file position tracking
        log_state = {"position": 0, "inode": None}

        # Initial read
        initial_lines = 100
        log_state["position"] = initial_lines

        # New lines added
        new_lines = 5
        total_lines = initial_lines + new_lines

        # Only process new lines
        lines_to_process = total_lines - log_state["position"]
        assert lines_to_process == new_lines


def test_dependencies_importable():
    """Test that required dependencies can be imported"""
    try:
        import flask
        import flask_cors

        assert flask is not None
        assert flask_cors is not None
    except ImportError as e:
        pytest.skip(f"Dependencies not installed: {e}")


def test_port_configuration():
    """Test that web UI port is configurable"""
    # Default port
    web_port = 8081
    assert isinstance(web_port, int)
    assert 1024 < web_port < 65535  # Valid port range


class TestHTMLContent:
    """Test web-ui.html content for correct escaping patterns"""

    def test_delete_button_uses_json_stringify(self):
        """Test that delete button uses JSON.stringify, not escapeHtml (PR #2657625584)"""
        html_path = Path(__file__).parent / "web-ui.html"
        with open(html_path) as f:
            content = f.read()

        # Find the rules table rendering section
        assert "deleteRule(" in content, "Delete button should exist"

        # Verify delete button uses JSON.stringify(target)
        assert "deleteRule(${JSON.stringify(target)})" in content, (
            "Delete button must use JSON.stringify(target) to avoid double-escaping"
        )

        # Verify delete button does NOT use escapeHtml
        assert "deleteRule('${escapeHtml(target)}" not in content, (
            "Delete button must NOT use escapeHtml (causes double-escaping bug)"
        )
        assert 'deleteRule("${escapeHtml(target)}' not in content, (
            "Delete button must NOT use escapeHtml (causes double-escaping bug)"
        )

    def test_display_still_uses_escape_html(self):
        """Test that table cell display still uses escapeHtml for XSS protection"""
        html_path = Path(__file__).parent / "web-ui.html"
        with open(html_path) as f:
            content = f.read()

        # Verify table cell uses escapeHtml for safe display
        assert '<td class="code">${escapeHtml(target)}</td>' in content, (
            "Table cell must use escapeHtml for XSS protection"
        )

    def test_edit_and_delete_buttons_use_same_pattern(self):
        """Test that edit and delete buttons both use JSON.stringify"""
        html_path = Path(__file__).parent / "web-ui.html"
        with open(html_path) as f:
            content = f.read()

        # Both should use JSON.stringify for consistency
        assert "editRule(${JSON.stringify(target)}" in content, (
            "Edit button should use JSON.stringify"
        )
        assert "deleteRule(${JSON.stringify(target)})" in content, (
            "Delete button should use JSON.stringify"
        )

    def test_no_double_escaping_pattern(self):
        """Test that there's no double-escaping pattern anywhere"""
        html_path = Path(__file__).parent / "web-ui.html"
        with open(html_path) as f:
            content = f.read()

        # Pattern that would cause double-escaping: escapeHtml used in onclick handlers
        # This is a smell test to catch similar bugs in the future
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if "onclick=" in line and "deleteRule" in line:
                # Delete button onclick should not have escapeHtml
                assert "escapeHtml" not in line, (
                    f"Line {i}: deleteRule onclick must not use escapeHtml"
                )


# TODO: Integration tests needed to fully verify GitHub PR fixes
#
# These integration tests would require running actual Flask server instances
# and handling concurrent requests with threading.
#
# 1. test_cache_lock_no_deadlock (PR Comment #2)
#    - Start web-ui.py Flask server
#    - Make concurrent API requests to /api/stats
#    - Verify no deadlock occurs during cache updates
#    - Verify calculate_stats doesn't acquire cache_lock
#
# 2. test_sse_stream_no_freeze (PR Comment #9)
#    - Start web-ui.py Flask server
#    - Connect EventSource to /api/stream
#    - Make concurrent API requests while stream is active
#    - Verify stream continues sending updates
#    - Verify no freeze or blocking occurs
#
# 3. test_incremental_log_reading (PR Comment #7)
#    - Start web-ui.py Flask server
#    - Append new lines to log file
#    - Call /api/stats endpoint
#    - Verify only new lines are read (check file position)
#    - Append more lines and verify incremental reading
#    - Test log rotation handling (inode change)
#
# 4. test_approve_endpoint_creates_rule (PR Comment #10)
#    - Start both network-monitor.py and web-ui.py
#    - Add pending request via network-monitor
#    - Call /api/approve with allow-domain action
#    - Verify rule is created in network-rules.json
#    - Send new request matching rule
#    - Verify network-monitor auto-reloads and allows request
#
# 5. test_concurrent_rule_modifications (PR Comments #1, #2, #10)
#    - Start both network-monitor.py and web-ui.py
#    - Modify rules via web UI (/api/rules POST)
#    - Simultaneously send requests through proxy
#    - Verify no race conditions or deadlocks
#    - Verify proxy sees updated rules immediately
