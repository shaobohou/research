#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "flask>=3.0.0",
#     "flask-cors>=4.0.0",
# ]
# ///

"""
Web-based UI for Network Firewall Management

Provides a browser-based interface for:
- Real-time network request monitoring
- Interactive rule management
- Statistics and analytics
- Live activity feed
"""

import json
import os
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Configuration
CONFIG_FILE = Path.home() / "docker-agent-data" / "network-rules.json"
LOG_FILE = Path.home() / "docker-agent-data" / "network-access.log"
PENDING_FILE = Path.home() / "docker-agent-data" / "network-pending.json"
WEB_PORT = 8081

app = Flask(__name__)
CORS(app)

# In-memory cache
cache = {
    "rules": {},
    "stats": defaultdict(int),
    "recent_requests": [],
    "pending_requests": [],
    "last_update": None,
}
cache_lock = threading.Lock()

# File position tracking for incremental log reading
log_state = {
    "position": 0,  # Last read position in file
    "inode": None,  # File inode to detect rotation
}
log_state_lock = threading.Lock()


def load_rules() -> dict[str, str]:
    """Load rules from config file"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading rules: {e}")
            return {}
    return {}


def save_rules(rules: dict[str, str]) -> bool:
    """Save rules to config file"""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(rules, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving rules: {e}")
        return False


def load_pending() -> list[dict]:
    """Load pending requests from file"""
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    if PENDING_FILE.exists():
        try:
            with open(PENDING_FILE) as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading pending requests: {e}")
            return []
    return []


def save_pending(pending: list[dict]) -> bool:
    """Save pending requests to file"""
    try:
        PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PENDING_FILE, "w") as f:
            json.dump(pending, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving pending requests: {e}")
        return False


def parse_log_line(line: str) -> dict | None:
    """Parse a log line into structured data"""
    try:
        parts = line.strip().split(" | ")
        if len(parts) >= 4:
            return {
                "timestamp": parts[0],
                "decision": parts[1].strip(),
                "method": parts[2].strip(),
                "url": parts[3].strip(),
            }
    except Exception:
        pass
    return None


def load_recent_logs(limit: int = 100) -> list[dict]:
    """Load recent requests from log file (optimized tail implementation)"""
    if not LOG_FILE.exists():
        return []

    try:
        # For files smaller than 1MB, just read the whole thing
        # For larger files, read last 100KB (should be enough for 100 lines)
        file_size = os.path.getsize(LOG_FILE)

        if file_size == 0:
            return []

        # Read last portion of file (or entire file if small)
        read_size = min(file_size, 100 * 1024)  # 100KB max

        with open(LOG_FILE, "rb") as f:
            f.seek(max(0, file_size - read_size))
            data = f.read()

        # Decode and split into lines
        text = data.decode("utf-8", errors="ignore")
        lines = text.split("\n")

        # Take last N non-empty lines and reverse (most recent first)
        recent_lines = [line for line in lines if line.strip()][-limit:]
        recent_lines.reverse()

        # Parse each line
        requests = []
        for line in recent_lines:
            parsed = parse_log_line(line)
            if parsed:
                requests.append(parsed)

        return requests

    except Exception as e:
        print(f"Error loading logs: {e}")
        return []


def calculate_stats(current_stats: dict | None = None) -> dict:
    """
    Calculate statistics from log file (OPTIMIZED: incremental reading).

    Only reads new lines since last call, tracking file position.
    Handles log rotation by detecting inode changes.

    Args:
        current_stats: Current stats dict to build upon (for incremental updates)
    """
    with log_state_lock:
        # Initialize from provided stats or empty dict
        stats = defaultdict(int, current_stats or {})

        if not LOG_FILE.exists():
            return dict(stats)

        try:
            # Get file info
            file_stat = os.stat(LOG_FILE)
            current_inode = file_stat.st_ino
            file_size = file_stat.st_size

            # Check if file was rotated/truncated (inode changed or size decreased)
            if log_state["inode"] != current_inode or file_size < log_state["position"]:
                # File was rotated - recalculate from scratch
                print("Log file rotation detected, recalculating stats...")
                stats = defaultdict(int)
                log_state["position"] = 0
                log_state["inode"] = current_inode

            # Read only new lines since last position
            with open(LOG_FILE) as f:
                f.seek(log_state["position"])

                for line in f:
                    parsed = parse_log_line(line)
                    if parsed:
                        stats["total"] += 1
                        stats[parsed["decision"].lower()] += 1

                # Update position for next read
                log_state["position"] = f.tell()
                log_state["inode"] = current_inode

            return dict(stats)

        except Exception as e:
            print(f"Error calculating stats: {e}")
            return dict(stats)


def update_cache():
    """Update in-memory cache from files"""
    with cache_lock:
        cache["rules"] = load_rules()
        # Pass current stats to avoid deadlock (don't acquire cache_lock in calculate_stats)
        cache["stats"] = calculate_stats(cache.get("stats", {}))
        cache["recent_requests"] = load_recent_logs(100)
        cache["pending_requests"] = load_pending()
        cache["last_update"] = datetime.now().isoformat()


# Background thread to update cache periodically
def cache_updater():
    """Background thread to refresh cache"""
    while True:
        try:
            update_cache()
        except Exception as e:
            print(f"Cache update error: {e}")
        time.sleep(2)  # Update every 2 seconds


# Start background updater
updater_thread = threading.Thread(target=cache_updater, daemon=True)
updater_thread.start()


# API Routes


@app.route("/")
def index():
    """Serve the main UI"""
    return send_from_directory(".", "web-ui.html")


@app.route("/api/rules", methods=["GET"])
def get_rules():
    """Get all firewall rules"""
    with cache_lock:
        return jsonify(
            {
                "rules": cache["rules"],
                "count": len(cache["rules"]),
                "last_update": cache["last_update"],
            }
        )


@app.route("/api/rules", methods=["POST"])
def add_rule():
    """Add or update a firewall rule"""
    data = request.json
    target = data.get("target")
    action = data.get("action")

    if not target or not action:
        return jsonify({"error": "Missing target or action"}), 400

    if action not in ["allow", "deny", "allow-domain", "deny-domain"]:
        return jsonify({"error": "Invalid action"}), 400

    with cache_lock:
        rules = cache["rules"].copy()
        rules[target] = action

        if save_rules(rules):
            cache["rules"] = rules
            return jsonify({"success": True, "target": target, "action": action})
        else:
            return jsonify({"error": "Failed to save rules"}), 500


@app.route("/api/rules/<path:target>", methods=["DELETE"])
def delete_rule(target):
    """Delete a firewall rule"""
    with cache_lock:
        rules = cache["rules"].copy()

        if target in rules:
            del rules[target]
            if save_rules(rules):
                cache["rules"] = rules
                return jsonify({"success": True, "target": target})
            else:
                return jsonify({"error": "Failed to save rules"}), 500
        else:
            return jsonify({"error": "Rule not found"}), 404


@app.route("/api/rules/clear", methods=["POST"])
def clear_rules():
    """Clear all firewall rules"""
    with cache_lock:
        if save_rules({}):
            cache["rules"] = {}
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to clear rules"}), 500


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get network access statistics"""
    with cache_lock:
        return jsonify({"stats": cache["stats"], "last_update": cache["last_update"]})


@app.route("/api/requests", methods=["GET"])
def get_requests():
    """Get recent network requests"""
    limit = request.args.get("limit", 100, type=int)

    with cache_lock:
        return jsonify(
            {
                "requests": cache["recent_requests"][:limit],
                "count": len(cache["recent_requests"]),
                "last_update": cache["last_update"],
            }
        )


@app.route("/api/pending", methods=["GET"])
def get_pending():
    """Get pending approval requests"""
    with cache_lock:
        return jsonify(
            {
                "pending": cache["pending_requests"],
                "count": len(cache["pending_requests"]),
                "last_update": cache["last_update"],
            }
        )


@app.route("/api/approve", methods=["POST"])
def approve_request():
    """Approve/deny a pending request and add firewall rule"""
    data = request.json
    host = data.get("host")
    url = data.get("url")
    action_type = data.get("action")  # allow-domain, deny-domain, allow-url, deny-url

    if not host or not url or not action_type:
        return jsonify({"error": "Missing required fields"}), 400

    if action_type not in ["allow-domain", "deny-domain", "allow-url", "deny-url"]:
        return jsonify({"error": "Invalid action"}), 400

    # Determine rule target and action
    if action_type in ["allow-domain", "deny-domain"]:
        target = host
        action = action_type
    else:  # allow-url or deny-url
        target = url
        action = "allow" if action_type == "allow-url" else "deny"

    # Add rule
    with cache_lock:
        rules = cache["rules"].copy()
        rules[target] = action

        # Remove from pending
        pending = cache["pending_requests"].copy()

        # For domain-level rules, clear ALL pending requests for that domain
        # For URL-level rules, only clear the specific URL
        if action_type in ["allow-domain", "deny-domain"]:
            # Clear all pending requests matching this host
            pending = [p for p in pending if p["host"] != host]
        else:
            # Clear only the specific URL
            pending = [p for p in pending if not (p["host"] == host and p["url"] == url)]

        # Save both
        if save_rules(rules) and save_pending(pending):
            cache["rules"] = rules
            cache["pending_requests"] = pending
            return jsonify({"success": True, "target": target, "action": action})
        else:
            return jsonify({"error": "Failed to save"}), 500


@app.route("/api/stream", methods=["GET"])
def stream_updates():
    """Server-Sent Events stream for live updates"""

    def generate():
        last_timestamp = None
        while True:
            with cache_lock:
                current_timestamp = cache["last_update"]
                if current_timestamp != last_timestamp:
                    data = {
                        "requests": cache["recent_requests"][:10],
                        "pending": cache["pending_requests"],
                        "stats": cache["stats"],
                        "timestamp": cache["last_update"],
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    last_timestamp = current_timestamp
            time.sleep(1)

    return app.response_class(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/export", methods=["GET"])
def export_rules():
    """Export rules as JSON"""
    with cache_lock:
        return jsonify(cache["rules"])


@app.route("/api/import", methods=["POST"])
def import_rules():
    """Import rules from JSON"""
    data = request.json

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid format, expected JSON object"}), 400

    # Validate all actions
    for target, action in data.items():
        if action not in ["allow", "deny", "allow-domain", "deny-domain"]:
            return jsonify({"error": f"Invalid action for {target}: {action}"}), 400

    with cache_lock:
        if save_rules(data):
            cache["rules"] = data
            return jsonify({"success": True, "count": len(data)})
        else:
            return jsonify({"error": "Failed to save rules"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "proxy_running": True,  # TODO: Actually check if proxy is running
            "rules_count": len(cache["rules"]),
            "timestamp": datetime.now().isoformat(),
        }
    )


if __name__ == "__main__":
    print("=" * 80)
    print("Network Firewall Web UI")
    print("=" * 80)
    print(f"Starting web server on http://0.0.0.0:{WEB_PORT}")
    print(f"Rules file: {CONFIG_FILE}")
    print(f"Log file: {LOG_FILE}")
    print()
    print(f"Open in browser: http://localhost:{WEB_PORT}")
    print("=" * 80)
    print()

    # Initial cache load
    update_cache()

    # Run Flask app
    app.run(host="0.0.0.0", port=WEB_PORT, debug=False, threaded=True)
