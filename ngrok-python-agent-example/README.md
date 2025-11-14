# ngrok Python Agent Example

A simple LLM agent with Flask and ngrok that demonstrates how to create a publicly accessible webhook-enabled AI agent.

## Overview

This example shows how to:
- Create a Flask-based web service with LLM integration
- Expose your local agent to the internet using ngrok
- Handle chat interactions and webhooks
- Maintain conversation history across sessions

## Features

- **Chat Endpoint**: POST to `/chat` to interact with the LLM agent
- **Webhook Support**: Receive and process webhook events at `/webhook`
- **Session Management**: Maintain separate conversation histories per session
- **ngrok Integration**: Automatically expose your local agent with a public URL
- **Fallback Mode**: Works in echo mode without OpenAI API key

## Prerequisites

- Python 3.8+
- ngrok account (free tier works fine)
- OpenAI API key (optional - runs in echo mode without it)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```bash
# Required for LLM functionality
OPENAI_API_KEY=sk-your-actual-api-key

# Optional but recommended for persistent ngrok URLs
NGROK_AUTH_TOKEN=your-ngrok-token

# Optional: customize the model
MODEL=gpt-3.5-turbo
```

**Getting API Keys:**
- OpenAI API: https://platform.openai.com/api-keys
- ngrok Auth Token: https://dashboard.ngrok.com/get-started/your-authtoken

### 3. Run the Agent

```bash
python agent.py
```

You should see output like:

```
🤖 Starting LLM Agent...
✅ OpenAI configured with model: gpt-3.5-turbo

============================================================
🚀 ngrok tunnel established!
📡 Public URL: https://abc123.ngrok-free.app
============================================================

🌐 Starting Flask server on http://localhost:5000
```

## Usage

### Health Check

```bash
curl https://your-ngrok-url.ngrok-free.app/
```

Response:
```json
{
  "status": "online",
  "message": "LLM Agent is running",
  "endpoints": {
    "/": "Health check",
    "/chat": "POST - Send a message to the agent",
    "/webhook": "POST - Receive webhook events",
    "/conversations/<session_id>": "GET - Retrieve conversation history"
  }
}
```

### Chat with the Agent

```bash
curl -X POST https://your-ngrok-url.ngrok-free.app/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, how are you?",
    "session_id": "user123"
  }'
```

Response:
```json
{
  "response": "Hello! I'm doing well, thank you for asking. How can I help you today?",
  "session_id": "user123",
  "model": "gpt-3.5-turbo",
  "tokens_used": 45
}
```

### View Conversation History

```bash
curl https://your-ngrok-url.ngrok-free.app/conversations/user123
```

Response:
```json
{
  "session_id": "user123",
  "messages": [
    {
      "role": "user",
      "content": "Hello, how are you?"
    },
    {
      "role": "assistant",
      "content": "Hello! I'm doing well, thank you for asking..."
    }
  ],
  "message_count": 2
}
```

### Clear Conversation History

```bash
curl -X DELETE https://your-ngrok-url.ngrok-free.app/conversations/user123
```

### Send Webhook Events

```bash
curl -X POST https://your-ngrok-url.ngrok-free.app/webhook \
  -H "Content-Type: application/json" \
  -H "X-Event-Type: custom.event" \
  -d '{
    "event": "user.signup",
    "user_id": "12345",
    "timestamp": "2024-01-15T10:30:00Z"
  }'
```

## API Endpoints

### `GET /`
Health check and endpoint documentation

### `POST /chat`
Send a message to the LLM agent

**Request Body:**
```json
{
  "message": "Your message here",
  "session_id": "optional-session-id"  // defaults to "default"
}
```

**Response:**
```json
{
  "response": "Agent's response",
  "session_id": "session-id",
  "model": "gpt-3.5-turbo",
  "tokens_used": 123
}
```

### `POST /webhook`
Receive webhook events from external services

**Request Body:** Any JSON payload

**Response:**
```json
{
  "status": "received",
  "event_type": "event-type-from-header",
  "message": "Webhook processed successfully"
}
```

### `GET /conversations/<session_id>`
Retrieve conversation history for a session

### `DELETE /conversations/<session_id>`
Clear conversation history for a session

## Configuration

Environment variables in `.env`:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for LLM functionality | - | No* |
| `NGROK_AUTH_TOKEN` | ngrok authentication token | - | No** |
| `MODEL` | OpenAI model to use | `gpt-3.5-turbo` | No |
| `USE_NGROK` | Enable/disable ngrok tunnel | `true` | No |
| `DEBUG` | Enable Flask debug mode | `false` | No |

\* Without OpenAI key, agent runs in echo mode
\*\* Without ngrok token, you get temporary URLs that change on restart

## Running Without ngrok

To run without ngrok (local only):

```bash
USE_NGROK=false python agent.py
```

Then access at `http://localhost:5000`

## Use Cases

### 1. GitHub Webhook Handler

Configure GitHub to send webhook events to your ngrok URL:
- Go to your repo → Settings → Webhooks
- Add webhook URL: `https://your-ngrok-url.ngrok-free.app/webhook`
- Select events to receive

### 2. Slack Bot Integration

Use the ngrok URL as your Slack app's Request URL for:
- Slash commands
- Interactive components
- Event subscriptions

### 3. Chat Interface Backend

Build a frontend chat interface that calls your agent's `/chat` endpoint

### 4. Testing Webhook Integrations

Test webhook integrations locally without deploying to production

## Development

### Project Structure

```
ngrok-python-agent-example/
├── agent.py              # Main agent script
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
└── README.md            # This file
```

### Adding Custom Endpoints

Add new Flask routes to `agent.py`:

```python
@app.route("/custom", methods=["POST"])
def custom_endpoint():
    data = request.get_json()
    # Your logic here
    return jsonify({"status": "success"})
```

### Extending the Agent

1. **Add Memory**: Integrate vector databases (Pinecone, Weaviate) for long-term memory
2. **Add Tools**: Use function calling to give the agent access to external tools
3. **Add Auth**: Implement API key authentication for production use
4. **Add Logging**: Use proper logging instead of print statements
5. **Add Database**: Store conversations in PostgreSQL/MongoDB instead of in-memory

## Troubleshooting

### ngrok Connection Issues

If ngrok fails to connect:
1. Check your auth token is correct
2. Verify you're not hitting ngrok's rate limits
3. Try running without ngrok: `USE_NGROK=false python agent.py`

### OpenAI API Errors

If you see OpenAI errors:
1. Verify your API key is valid
2. Check you have credits in your OpenAI account
3. Try a different model (e.g., `gpt-3.5-turbo` instead of `gpt-4`)

### Port Already in Use

If port 5000 is already in use:
```python
# Modify agent.py:
app.run(host="0.0.0.0", port=5001)  # Change port
```

## Security Considerations

**This is a development example. For production:**

1. **Add Authentication**: Implement API key validation
2. **Rate Limiting**: Add rate limiting to prevent abuse
3. **Input Validation**: Validate and sanitize all inputs
4. **HTTPS Only**: Use ngrok's TLS endpoints
5. **Secrets Management**: Use proper secrets management (not .env files)
6. **CORS**: Configure CORS properly if used with web frontends

## Resources

- [ngrok Documentation](https://ngrok.com/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [pyngrok Documentation](https://pyngrok.readthedocs.io/)

## License

This example is provided as-is for educational purposes.

## Next Steps

1. Add authentication to secure your endpoints
2. Implement persistent storage (database) for conversations
3. Add support for multiple LLM providers (Anthropic, Cohere, etc.)
4. Create a web frontend for the chat interface
5. Add streaming responses for better UX
6. Implement function calling for tool use
7. Add observability (logging, metrics, tracing)
