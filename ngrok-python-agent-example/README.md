# ngrok Python Agent Example

A simple, extensible LLM agent with Flask and ngrok that demonstrates how to create a publicly accessible webhook-enabled AI agent.

## Overview

This example shows how to:
- Create a Flask-based web service with LLM integration
- Use an abstraction layer for clean agent implementation
- Expose your local agent to the internet using ngrok
- Handle chat interactions and webhooks
- Maintain conversation history across sessions

## Features

- **Clean Agent Abstraction**: Simple, extensible agent interface
- **Chat Endpoint**: POST to `/chat` to interact with the LLM agent
- **Webhook Support**: Receive and process webhook events at `/webhook`
- **Session Management**: Maintain separate conversation histories per session
- **ngrok Integration**: Automatically expose your local agent with a public URL

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- ngrok account (free tier works fine)
- OpenAI API key

## Setup

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:

```bash
OPENAI_API_KEY=sk-your-actual-api-key
NGROK_AUTH_TOKEN=your-ngrok-token  # Optional
```

**Getting API Keys:**
- OpenAI API: https://platform.openai.com/api-keys
- ngrok Auth Token: https://dashboard.ngrok.com/get-started/your-authtoken

### 3. Run the Agent

```bash
uv run agent.py
```

You should see output like:

```
🤖 Starting LLM Agent...
✅ Agent: llm-gpt-3.5-turbo

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
  "agent": "llm-gpt-3.5-turbo",
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
  "agent": "llm-gpt-3.5-turbo",
  "model": "gpt-3.5-turbo",
  "tokens_used": 45,
  "finish_reason": "stop"
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
  "agent": "llm-model-name",
  "model": "gpt-3.5-turbo",
  "tokens_used": 123,
  "finish_reason": "stop"
}
```

### `POST /webhook`
Receive webhook events from external services

### `GET /conversations/<session_id>`
Retrieve conversation history for a session

### `DELETE /conversations/<session_id>`
Clear conversation history for a session

## Agent Abstraction

### Architecture

The agent system uses a clean Protocol-based interface:

```
agents.py
├── Agent (Protocol defining the interface)
├── Message (conversation message)
├── AgentResponse (standardized response)
├── LLMAgent (OpenAI-based implementation)
├── create_agent() (factory function)
└── create_agent_from_env() (factory from environment)
```

### Core Components

**`Agent`**: Protocol defining the agent interface (duck-typed)
- `chat(message, history) -> AgentResponse`: Process messages
- `name`: Agent identifier

**`Message`**: Represents a conversation message with role and content

**`AgentResponse`**: Standardized response with content and metadata

**`LLMAgent`**: Implementation using OpenAI's Chat Completions API

### Creating Custom Agents

Implement the `Agent` protocol to create custom agents (no inheritance needed):

```python
from agents import AgentResponse

class CustomAgent:
    """Custom agent - automatically satisfies Agent protocol"""

    def chat(self, message, history=None):
        # Your custom logic here
        response_text = f"Custom response to: {message}"

        return AgentResponse(
            content=response_text,
            metadata={"custom_field": "value"}
        )

    @property
    def name(self):
        return "custom-agent"

# Use your custom agent - works with type hints thanks to Protocol
agent = CustomAgent()
response = agent.chat("Hello!")
```

### Using the Agent Programmatically

```python
from agents import create_agent, Message

# Create agent with custom config
agent = create_agent({
    "api_key": "sk-...",
    "model": "gpt-4",
    "max_tokens": 1000,
    "temperature": 0.5
})

# Or from environment variables
agent = create_agent_from_env()

# Chat with history
history = [
    Message("user", "What is Python?"),
    Message("assistant", "Python is a programming language...")
]

response = agent.chat("Tell me more", history=history)
print(response.content)
print(response.metadata)  # tokens_used, finish_reason, etc.
```

## Configuration

### Environment Variables

Only secrets need to be in `.env`:

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `NGROK_AUTH_TOKEN` | ngrok authentication token | No* |

\* Without ngrok token, you get temporary URLs that change on restart

### Configuration Defaults

Defaults are defined in the code and can be overridden via environment variables:

**LLM Configuration** (in `agents.py`):
- `MODEL` - Default: `gpt-3.5-turbo`
- `MAX_TOKENS` - Default: `500`
- `TEMPERATURE` - Default: `0.7`

**Server Configuration** (in `agent.py`):
- `USE_NGROK` - Default: `true`
- `DEBUG` - Default: `false`

### Overriding Defaults

Override defaults by setting environment variables:

```bash
# In your shell or .env file
export MODEL=gpt-4
export MAX_TOKENS=1000
export TEMPERATURE=0.5
export USE_NGROK=false
export DEBUG=true
```

Or programmatically:

```python
from agents import create_agent

agent = create_agent({
    "model": "gpt-4",
    "max_tokens": 1000,
    "temperature": 0.5
})
```

## Running Without ngrok

To run without ngrok (local only):

```bash
export USE_NGROK=false
uv run agent.py
```

Or set in your `.env`:
```bash
USE_NGROK=false
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

```bash
uv add package-name
```

### Extending the System

1. **Add Memory**: Integrate vector databases (Pinecone, Weaviate) for long-term memory
2. **Add Tools**: Implement function calling in your custom agent
3. **Add Auth**: Implement API key authentication for production use
4. **Add Logging**: Use proper logging instead of print statements
5. **Add Database**: Store conversations in PostgreSQL/MongoDB instead of in-memory
6. **Add Streaming**: Implement streaming responses for better UX

### Custom Agent Example: Function Calling

```python
from agents import AgentResponse, Message

class ToolAgent:
    """Agent with tool-calling capabilities - implements Agent protocol"""

    def __init__(self, config=None):
        self.config = config or {}
        self.tools = {
            "get_weather": self._get_weather,
            "calculate": self._calculate
        }

    def _get_weather(self, location):
        # Your weather API logic
        return f"Weather in {location}: Sunny, 72°F"

    def _calculate(self, expression):
        # Safe calculation logic
        return str(eval(expression))

    def chat(self, message, history=None):
        # Parse message for tool calls
        # Execute tools
        # Return response
        return AgentResponse(
            content="Tool execution result",
            metadata={"tools_used": ["get_weather"]}
        )

    @property
    def name(self):
        return "tool-agent"
```

## Troubleshooting

### ngrok Connection Issues

If ngrok fails to connect:
1. Check your auth token is correct in `.env`
2. Verify you're not hitting ngrok's rate limits
3. Try running without ngrok: Set `USE_NGROK=false` in `.env` or environment

### OpenAI API Errors

If you see API errors:
1. Verify your API key is valid (starts with `sk-`)
2. Check you have credits in your OpenAI account
3. Try a different model (e.g., `gpt-3.5-turbo` is cheaper than `gpt-4`)
4. Check the error message for rate limits or quota issues

### Import Errors

If you see import errors:
1. Make sure you ran `uv sync` to install dependencies
2. Check that you're running with `uv run agent.py`

### Port Already in Use

If port 5000 is already in use, modify `agent.py`:
```python
app.run(host="0.0.0.0", port=5001)  # Change port
```

And update ngrok connection:
```python
public_url = ngrok.connect(5001)  # Match the port
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
- [pyngrok Documentation](https://pyngrok.readthedocs.io/)

## License

This example is provided as-is for educational purposes.

## Next Steps

1. Implement custom agent with your own logic
2. Add function calling/tool use capabilities
3. Add persistent storage (database) for conversations
4. Create a web frontend for the chat interface
5. Add streaming responses for better UX
6. Implement RAG (retrieval-augmented generation)
7. Add observability (logging, metrics, tracing)
8. Deploy to production with proper authentication
