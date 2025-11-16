#!/usr/bin/env python3
"""Minimal Flask + ngrok agent scaffold."""

import logging
import threading
import uuid

from absl import app as absl_app
from absl import flags
from flask import Flask, jsonify, request

from agents import Message, create_agent_from_env

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False  # Disable unicode escaping for better readability

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration via absl.flags
FLAGS = flags.FLAGS
flags.DEFINE_string(
    "host",
    "0.0.0.0",
    "Host interface that the Flask development server binds to.",
)
flags.DEFINE_integer("port", 5050, "Port exposed by the Flask development server.")
flags.DEFINE_bool("debug", False, "Run the Flask development server in debug mode.")

# Validation guardrails
MAX_MESSAGE_LENGTH = 1_000_000

# Simple in-memory conversation history
# Structure: {session_id: [Message, Message, ...]}
conversations: dict[str, list[Message]] = {}
conversations_lock = threading.Lock()


def _valid_session_id(session_id: str) -> bool:
    """Session IDs: 1-128 chars, alphanumeric and hyphens only."""

    if not session_id or len(session_id) > 128:
        return False
    return all(char.isalnum() or char == "-" for char in session_id)


def _get_history(session_id: str) -> list[Message]:
    """Return a copy of the conversation history for a session (creating it if needed)."""

    with conversations_lock:
        return conversations.setdefault(session_id, []).copy()


def _peek_conversation(session_id: str) -> list[Message] | None:
    """Return a copy of the stored conversation without creating it."""

    with conversations_lock:
        history = conversations.get(session_id)
        return history.copy() if history is not None else None


def _clear_conversation(session_id: str) -> bool:
    """Clear a stored conversation if it exists."""

    with conversations_lock:
        return conversations.pop(session_id, None) is not None


def _store_messages(session_id: str, user_message: str, response: str) -> None:
    """Persist the latest user/assistant turns."""

    with conversations_lock:
        history = conversations.setdefault(session_id, [])
        history.append(Message("user", user_message))
        history.append(Message("assistant", response))


@app.get("/")
def home():
    """Rich health check with endpoint documentation."""

    return jsonify(
        {
            "status": "online",
            "agent": app.config["agent"].name,
            "message": "Agent is running",
            "max_message_length": MAX_MESSAGE_LENGTH,
            "endpoints": {
                "/": "Health check",
                "/chat": "POST - send a message to the agent",
                "/webhook": "POST - receive generic webhook events",
                "/conversations/<session_id>": "GET to inspect, DELETE to clear history",
            },
        }
    )


@app.post("/chat")
def chat():
    """
    Chat endpoint for interacting with the agent

    Expected JSON payload:
    {
        "message": "Your message here",
        "session_id": "optional-session-id"
    }
    """
    try:
        data = request.get_json()

        if not data or "message" not in data:
            return jsonify({"error": "Missing 'message' in request"}), 400

        user_message = data["message"]

        # Validate message type
        if not isinstance(user_message, str):
            return jsonify({"error": "Message must be a string"}), 400

        # Validate message length
        if len(user_message) > MAX_MESSAGE_LENGTH:
            return jsonify({"error": f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters"}), 400

        # Generate UUID for session if not provided
        session_id = data.get("session_id") or str(uuid.uuid4())

        # Validate session_id format (alphanumeric and hyphens only)
        if not isinstance(session_id, str) or not _valid_session_id(session_id):
            return jsonify({"error": "Invalid session_id format"}), 400

        # Get agent response with thread-safe conversation history access
        try:
            history = _get_history(session_id)

            response = app.config["agent"].chat(message=user_message, history=history)

            _store_messages(session_id, user_message, response.content)

            return jsonify(
                {
                    "response": response.content,
                    "session_id": session_id,
                    "agent": app.config["agent"].name,
                    **response.metadata,
                }
            )

        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            return jsonify({"error": "Failed to process message"}), 500

    except Exception as e:
        logger.error(f"Request error: {e}", exc_info=True)
        return jsonify({"error": "Invalid request"}), 400


@app.post("/webhook")
def webhook():
    """Generic webhook endpoint for receiving events."""

    try:
        data = request.get_json(silent=True)
        headers = dict(request.headers)

        logger.info("Webhook received")
        logger.debug("Headers: %s", headers)
        logger.debug("Payload: %s", data)

        event_type = headers.get("X-Event-Type", "unknown")

        return jsonify(
            {
                "status": "received",
                "event_type": event_type,
                "message": "Webhook processed successfully",
            }
        )

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return jsonify({"error": "Failed to process webhook"}), 500


@app.get("/conversations/<session_id>")
def get_conversation(session_id: str):
    """Retrieve stored conversation history for a session."""

    if not _valid_session_id(session_id):
        return jsonify({"error": "Invalid session_id format"}), 400

    history = _peek_conversation(session_id)
    if history is None:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(
        {
            "session_id": session_id,
            "messages": [msg.to_dict() for msg in history],
            "message_count": len(history),
        }
    )


@app.delete("/conversations/<session_id>")
def clear_conversation(session_id: str):
    """Clear stored conversation history for a session."""

    if not _valid_session_id(session_id):
        return jsonify({"error": "Invalid session_id format"}), 400

    if _clear_conversation(session_id):
        return jsonify({"message": f"Conversation {session_id} cleared"})

    return jsonify({"error": "Session not found"}), 404


def main(argv: list[str]) -> None:
    """Main entry point."""

    # Initialize agent after flags are parsed
    app.config["agent"] = create_agent_from_env()

    logger.info("🤖 Starting Agent...")
    logger.info(f"✅ Agent: {app.config['agent'].name}")
    logger.info("")
    logger.info("⚙️  Configuration:")
    logger.info(f"   Host: {FLAGS.host}")
    logger.info(f"   Port: {FLAGS.port}")
    logger.info(f"   Debug: {FLAGS.debug}")
    logger.info(f"   Max message length: {MAX_MESSAGE_LENGTH:,}")
    logger.info("")
    logger.info("🔌 Bring your own ngrok CLI tunnel. See README for details.")
    logger.info("🌐 Starting Flask server on http://%s:%s", FLAGS.host, FLAGS.port)
    logger.info("Press Ctrl+C to stop the server")

    app.run(host=FLAGS.host, port=FLAGS.port, debug=FLAGS.debug)


if __name__ == "__main__":
    absl_app.run(main)
