#!/usr/bin/env python3
"""
Simple LLM Agent with ngrok exposure
Demonstrates how to create a webhook-enabled LLM agent accessible via ngrok tunnel
"""

import os
import sys
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
MODEL = os.getenv("MODEL", "gpt-3.5-turbo")

# Initialize OpenAI client (if key is provided)
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Simple in-memory conversation history
conversations = {}


@app.route("/")
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "online",
        "message": "LLM Agent is running",
        "endpoints": {
            "/": "Health check",
            "/chat": "POST - Send a message to the agent",
            "/webhook": "POST - Receive webhook events",
            "/conversations/<session_id>": "GET - Retrieve conversation history"
        }
    })


@app.route("/chat", methods=["POST"])
def chat():
    """
    Chat endpoint for interacting with the LLM agent

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
        session_id = data.get("session_id", "default")

        # Initialize conversation history for this session
        if session_id not in conversations:
            conversations[session_id] = []

        # Add user message to history
        conversations[session_id].append({
            "role": "user",
            "content": user_message
        })

        # Check if OpenAI is configured
        if not OPENAI_API_KEY:
            # Fallback: Simple echo response
            response_text = f"Echo (OpenAI not configured): {user_message}"
            conversations[session_id].append({
                "role": "assistant",
                "content": response_text
            })

            return jsonify({
                "response": response_text,
                "session_id": session_id,
                "mode": "echo"
            })

        # Call OpenAI API
        try:
            response = openai.ChatCompletion.create(
                model=MODEL,
                messages=conversations[session_id],
                max_tokens=500,
                temperature=0.7
            )

            assistant_message = response.choices[0].message.content

            # Add assistant response to history
            conversations[session_id].append({
                "role": "assistant",
                "content": assistant_message
            })

            return jsonify({
                "response": assistant_message,
                "session_id": session_id,
                "model": MODEL,
                "tokens_used": response.usage.total_tokens
            })

        except Exception as e:
            return jsonify({
                "error": f"OpenAI API error: {str(e)}"
            }), 500

    except Exception as e:
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

        print(f"Webhook received:")
        print(f"Headers: {headers}")
        print(f"Payload: {data}")

        # Process webhook event (customize based on your needs)
        event_type = headers.get("X-Event-Type", "unknown")

        return jsonify({
            "status": "received",
            "event_type": event_type,
            "message": "Webhook processed successfully"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/conversations/<session_id>", methods=["GET"])
def get_conversation(session_id):
    """Retrieve conversation history for a session"""
    if session_id not in conversations:
        return jsonify({"error": "Session not found"}), 404

    return jsonify({
        "session_id": session_id,
        "messages": conversations[session_id],
        "message_count": len(conversations[session_id])
    })


@app.route("/conversations/<session_id>", methods=["DELETE"])
def clear_conversation(session_id):
    """Clear conversation history for a session"""
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
        print(f"\n{'='*60}")
        print(f"🚀 ngrok tunnel established!")
        print(f"📡 Public URL: {public_url}")
        print(f"{'='*60}\n")

        return public_url

    except ImportError:
        print("⚠️  pyngrok not installed. Install with: pip install pyngrok")
        print("Running without ngrok tunnel...")
        return None
    except Exception as e:
        print(f"⚠️  Failed to start ngrok: {e}")
        print("Running without ngrok tunnel...")
        return None


def main():
    """Main entry point"""
    print("\n🤖 Starting LLM Agent...")

    # Check configuration
    if not OPENAI_API_KEY:
        print("⚠️  OPENAI_API_KEY not set - running in echo mode")
    else:
        print(f"✅ OpenAI configured with model: {MODEL}")

    # Start ngrok tunnel
    use_ngrok = os.getenv("USE_NGROK", "true").lower() == "true"
    if use_ngrok:
        public_url = start_ngrok()

    # Start Flask app
    print("\n🌐 Starting Flask server on http://localhost:5000")
    print("\nPress Ctrl+C to stop the server\n")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=os.getenv("DEBUG", "false").lower() == "true"
    )


if __name__ == "__main__":
    main()
