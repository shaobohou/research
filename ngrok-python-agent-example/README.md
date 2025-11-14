# ngrok Python Agent Example

A simple, extensible LLM agent with Flask and ngrok that demonstrates how to create a publicly accessible webhook-enabled AI agent with pluggable LLM providers.

## Overview

This example shows how to:
- Create a Flask-based web service with LLM integration
- Use an abstraction layer to support multiple LLM providers
- Expose your local agent to the internet using ngrok
- Handle chat interactions and webhooks
- Maintain conversation history across sessions

## Features

- **Pluggable Agent System**: Easily swap between OpenAI, Anthropic, or custom agents
- **Chat Endpoint**: POST to `/chat` to interact with the LLM agent
- **Webhook Support**: Receive and process webhook events at `/webhook`
- **Session Management**: Maintain separate conversation histories per session
- **ngrok Integration**: Automatically expose your local agent with a public URL
- **Fallback Mode**: Works in echo mode without API keys

## Prerequisites

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) package manager
- ngrok account (free tier works fine)
- LLM API key - OpenAI or Anthropic (optional - runs in echo mode without it)

## Setup

### 1. Install Dependencies

Install base dependencies (Flask, ngrok, python-dotenv):

```bash
uv sync
```

Install with your preferred LLM provider:

```bash
# For OpenAI
uv sync --extra openai

# For Anthropic
uv sync --extra anthropic

# For all providers
uv sync --extra all
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and configure your agent:

```bash
# Choose your agent provider
AGENT_PROVIDER=openai  # or anthropic, or echo

# Add your API key
OPENAI_API_KEY=sk-your-actual-api-key

# Optional: customize the model and parameters
MODEL=gpt-3.5-turbo
MAX_TOKENS=500
TEMPERATURE=0.7
```

**Getting API Keys:**
- OpenAI API: https://platform.openai.com/api-keys
- Anthropic API: https://console.anthropic.com/
- ngrok Auth Token: https://dashboard.ngrok.com/get-started/your-authtoken

### 3. Run the Agent

```bash
uv run agent.py
```

You should see output like:

```
🤖 Starting LLM Agent...
✅ Agent: openai-gpt-3.5-turbo

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
  "agent": "openai-gpt-3.5-turbo",
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
  "agent": "openai-gpt-3.5-turbo",
  "provider": "openai",
  "model": "gpt-3.5-turbo",
  "tokens_used": 45
}
```

### View Conversation History

```bash
curl https://your-ngrok-url.ngrok-free.app/conversations/user123
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
    "user_id": "12345"
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
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "response": "Agent's response",
  "session_id": "session-id",
  "agent": "provider-model",
  "provider": "openai",
  "model": "gpt-3.5-turbo",
  "tokens_used": 123
}
```

### `POST /webhook`
Receive webhook events from external services

### `GET /conversations/<session_id>`
Retrieve conversation history for a session

### `DELETE /conversations/<session_id>`
Clear conversation history for a session

## Agent Abstraction System

### Architecture

The agent system uses a clean abstraction layer to support multiple LLM providers:

```
agents.py
├── AgentBase (abstract base class)
├── Message (conversation message)
├── AgentResponse (standardized response)
├── EchoAgent (simple fallback)
├── OpenAIAgent (OpenAI integration)
├── AnthropicAgent (Anthropic integration)
└── AgentFactory (creates agents)
```

### Supported Providers

#### OpenAI
```bash
AGENT_PROVIDER=openai
OPENAI_API_KEY=sk-...
MODEL=gpt-3.5-turbo  # or gpt-4, gpt-4-turbo-preview
```

#### Anthropic
```bash
AGENT_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
MODEL=claude-3-5-sonnet-20241022  # or claude-3-opus-20240229
```

#### Echo (Fallback)
```bash
AGENT_PROVIDER=echo
# No API key needed
```

### Creating Custom Agents

Create a custom agent by extending `AgentBase`:

```python
from agents import AgentBase, AgentResponse, AgentFactory

class CustomAgent(AgentBase):
    def chat(self, message, history=None):
        # Your custom logic here
        response_text = f"Custom response to: {message}"

        return AgentResponse(
            content=response_text,
            metadata={"provider": "custom"}
        )

    @property
    def name(self):
        return "custom-agent"

# Register your agent
AgentFactory.register("custom", CustomAgent)
```

Then use it:
```bash
AGENT_PROVIDER=custom
```

### Agent Interface

All agents implement:

**`chat(message: str, history: List[Message]) -> AgentResponse`**
- Process a message and return a response
- `history` contains previous conversation messages
- Returns `AgentResponse` with content and metadata

**`name: str`**
- Identifier for the agent (e.g., "openai-gpt-4")

## Configuration

Environment variables in `.env`:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `AGENT_PROVIDER` | Which LLM provider to use | `openai` | No |
| `OPENAI_API_KEY` | OpenAI API key | - | If using OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic API key | - | If using Anthropic |
| `MODEL` | Model to use | `gpt-3.5-turbo` | No |
| `MAX_TOKENS` | Maximum tokens in response | `500` | No |
| `TEMPERATURE` | Temperature for generation | `0.7` | No |
| `NGROK_AUTH_TOKEN` | ngrok authentication token | - | No* |
| `USE_NGROK` | Enable/disable ngrok tunnel | `true` | No |
| `DEBUG` | Enable Flask debug mode | `false` | No |

\* Without ngrok token, you get temporary URLs that change on restart

## Running Without ngrok

To run without ngrok (local only):

```bash
USE_NGROK=false uv run agent.py
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
├── agent.py              # Main Flask application
├── agents.py             # Agent abstraction layer
├── pyproject.toml        # Project metadata and dependencies
├── .env.example         # Environment variables template
└── README.md            # This file
```

### Adding Custom Endpoints

Add new Flask routes to `agent.py`:

```python
@app.route("/custom", methods=["POST"])
def custom_endpoint():
    data = request.get_json()
    # Use the agent
    response = agent.chat(data["message"])
    return jsonify({"result": response.content})
```

### Adding Dependencies

Add a package to the project:

```bash
uv add package-name
```

Add a package as an optional dependency group:

```bash
# Add to pyproject.toml [project.optional-dependencies]
# Then users can install with: uv sync --extra your-group
```

### Extending the System

1. **Add Memory**: Integrate vector databases (Pinecone, Weaviate) for long-term memory
2. **Add Tools**: Implement function calling in your custom agent
3. **Add Auth**: Implement API key authentication for production use
4. **Add Logging**: Use proper logging instead of print statements
5. **Add Database**: Store conversations in PostgreSQL/MongoDB instead of in-memory
6. **Add Streaming**: Implement streaming responses for better UX

## Troubleshooting

### ngrok Connection Issues

If ngrok fails to connect:
1. Check your auth token is correct
2. Verify you're not hitting ngrok's rate limits
3. Try running without ngrok: `USE_NGROK=false uv run agent.py`

### LLM Provider Errors

If you see API errors:
1. Verify your API key is valid and in the correct format
2. Check you have credits in your account
3. Try a different model
4. Check the error message for rate limits or quota issues

### Agent Falls Back to Echo

If the agent automatically uses echo mode:
1. Check that your API key is set in `.env`
2. Verify `AGENT_PROVIDER` is set correctly
3. Ensure the LLM package is installed (should be automatic with `uv sync`)

### Port Already in Use

If port 5000 is already in use, modify `agent.py`:
```python
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
7. **Logging**: Implement proper audit logging
8. **Error Handling**: Don't expose internal errors to users

## Resources

- [uv Documentation](https://github.com/astral-sh/uv)
- [ngrok Documentation](https://ngrok.com/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Anthropic API Reference](https://docs.anthropic.com/)
- [pyngrok Documentation](https://pyngrok.readthedocs.io/)

## License

This example is provided as-is for educational purposes.

## Next Steps

1. Add your favorite LLM provider by extending `AgentBase`
2. Implement function calling/tool use in a custom agent
3. Add persistent storage (database) for conversations
4. Create a web frontend for the chat interface
5. Add streaming responses for better UX
6. Implement RAG (retrieval-augmented generation)
7. Add observability (logging, metrics, tracing)
8. Deploy to production with proper authentication
