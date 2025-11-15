#!/usr/bin/env python3
"""
Simple Agent Scaffolding with ngrok exposure
Demonstrates how to create a webhook-enabled conversational agent accessible via ngrok tunnel
"""

import os
import uuid
import logging
import threading
from flask import Flask, request, jsonify

from agents import create_agent_from_env, Message

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
USE_NGROK = os.getenv("USE_NGROK", "true").lower() == "true"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
MAX_MESSAGE_LENGTH = 10000

# Initialize agent
agent = create_agent_from_env()

# Simple in-memory conversation history
# Structure: {session_id: [Message, Message, ...]}
conversations = {}
conversations_lock = threading.Lock()


@app.route("/")
def home():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "online",
            "agent": agent.name,
            "message": "Agent is running",
            "endpoints": {
                "/": "Health check",
                "/chat": "POST - Send a message to the agent",
                "/webhook": "POST - Receive webhook events",
                "/conversations/<session_id>": "GET to retrieve, DELETE to clear conversation history",
            },
        }
    )


@app.route("/chat", methods=["POST"])
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

        # Validate message length
        if not isinstance(user_message, str) or len(user_message) > MAX_MESSAGE_LENGTH:
            return jsonify(
                {"error": f"Message must be a string with max length {MAX_MESSAGE_LENGTH}"}
            ), 400

        # Generate UUID for session if not provided
        session_id = data.get("session_id")
        if session_id is None:
            session_id = str(uuid.uuid4())

        # Validate session_id format (alphanumeric and hyphens only)
        if not isinstance(session_id, str) or not all(c.isalnum() or c == "-" for c in session_id):
            return jsonify({"error": "Invalid session_id format"}), 400

        # Get agent response with thread-safe conversation history access
        try:
            with conversations_lock:
                # Initialize conversation history for this session
                if session_id not in conversations:
                    conversations[session_id] = []

                # Get conversation history for this session
                history = conversations[session_id].copy()

            # Call agent outside the lock to avoid holding it during API call
            response = agent.chat(message=user_message, history=history)

            # Add user message and agent response to history
            with conversations_lock:
                conversations[session_id].append(Message("user", user_message))
                conversations[session_id].append(Message("assistant", response.content))

            return jsonify(
                {
                    "response": response.content,
                    "session_id": session_id,
                    "agent": agent.name,
                    **response.metadata,
                }
            )

        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            return jsonify({"error": f"Agent error: {str(e)}"}), 500

    except Exception as e:
        logger.error(f"Request error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Generic webhook endpoint for receiving events
    Can be used for GitHub webhooks, Slack events, etc.
    """
    try:
        data = request.get_json()
        headers = dict(request.headers)

        logger.info("Webhook received")
        logger.debug(f"Headers: {headers}")
        logger.debug(f"Payload: {data}")

        # Process webhook event (customize based on your needs)
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
        return jsonify({"error": str(e)}), 500


@app.route("/conversations/<session_id>", methods=["GET"])
def get_conversation(session_id):
    """Retrieve conversation history for a session"""
    with conversations_lock:
        if session_id not in conversations:
            return jsonify({"error": "Session not found"}), 404

        messages = [msg.to_dict() for msg in conversations[session_id]]
        message_count = len(conversations[session_id])

    return jsonify(
        {
            "session_id": session_id,
            "messages": messages,
            "message_count": message_count,
        }
    )


@app.route("/conversations/<session_id>", methods=["DELETE"])
def clear_conversation(session_id):
    """Clear conversation history for a session"""
    with conversations_lock:
        if session_id in conversations:
            del conversations[session_id]
            return jsonify({"message": f"Conversation {session_id} cleared"})

        return jsonify({"error": "Session not found"}), 404


def start_ngrok():
    """Start ngrok tunnel"""
    try:
        from pyngrok import ngrok

        # Authenticate if token is provided
        if NGROK_AUTH_TOKEN:
            ngrok.set_auth_token(NGROK_AUTH_TOKEN)

        # Open a HTTP tunnel on the default port 5000
        public_url = ngrok.connect(5000)
        logger.info("=" * 60)
        logger.info("🚀 ngrok tunnel established!")
        logger.info(f"📡 Public URL: {public_url}")
        logger.info("=" * 60)

        return public_url

    except ImportError:
        logger.warning("pyngrok not installed. Install with: uv add pyngrok")
        logger.warning("Running without ngrok tunnel...")
        return None
    except Exception as e:
        logger.warning(f"Failed to start ngrok: {e}")
        logger.warning("Running without ngrok tunnel...")
        return None


def main():
    """Main entry point"""
    logger.info("🤖 Starting Agent...")
    logger.info(f"✅ Agent: {agent.name}")

    # Start ngrok tunnel
    if USE_NGROK:
        start_ngrok()

    # Start Flask app
    logger.info("🌐 Starting Flask server on http://localhost:5000")
    logger.info("Press Ctrl+C to stop the server")

    app.run(host="0.0.0.0", port=5000, debug=DEBUG)


if __name__ == "__main__":
    main()
