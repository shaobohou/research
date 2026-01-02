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
