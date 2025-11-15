# ngrok Python Agent Example

A simple, extensible agent scaffolding with Flask and ngrok that demonstrates how to create a publicly accessible webhook-enabled conversational agent.

## Overview

This example shows how to:
- Create a Flask-based web service with agent integration
- Use a Protocol-based abstraction layer for clean agent implementation
- Expose your local agent to the internet using ngrok
- Handle chat interactions and webhooks
- Maintain conversation history across sessions

## Features

- **Clean Agent Abstraction**: Protocol-based interface (no inheritance needed)
- **Chat Endpoint**: POST to `/chat` to interact with the agent
- **Webhook Support**: Receive and process webhook events at `/webhook`
- **Session Management**: Automatic UUID-based session IDs with conversation history
- **Thread Safety**: Thread-safe conversation storage with proper locking
- **ngrok Integration**: Automatically expose your local agent with a public URL
- **Input Validation**: Message length limits and session ID validation

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- ngrok account (free tier works fine)

## Setup

### 1. Install Dependencies

```bash
uv sync
```

### 2. Set Environment Variables (Optional)

```bash
export NGROK_AUTH_TOKEN=your-ngrok-token  # For persistent ngrok URLs
export USE_NGROK=true                     # Enable/disable ngrok (default: true)
export DEBUG=false                        # Enable Flask debug mode (default: false)
```

**Getting ngrok Auth Token:**
- ngrok Auth Token: https://dashboard.ngrok.com/get-started/your-authtoken

### 3. Run the Agent

```bash
uv run agent.py
```

You should see output like:

```
INFO:__main__:🤖 Starting Agent...
INFO:__main__:✅ Agent: echo-agent
INFO:__main__:============================================================
INFO:__main__:🚀 ngrok tunnel established!
INFO:__main__:📡 Public URL: https://abc123.ngrok-free.app
INFO:__main__:============================================================
INFO:__main__:🌐 Starting Flask server on http://localhost:5000
INFO:__main__:Press Ctrl+C to stop the server
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
  "agent": "echo-agent",
  "message": "Agent is running",
  "endpoints": {
    "/": "Health check",
    "/chat": "POST - Send a message to the agent",
    "/webhook": "POST - Receive webhook events",
    "/conversations/<session_id>": "GET to retrieve, DELETE to clear conversation history"
  }
}
```

### Chat with the Agent

Without session ID (auto-generated UUID):
```bash
curl -X POST https://your-ngrok-url.ngrok-free.app/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, how are you?"
  }'
```

With explicit session ID:
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
  "response": "Echo: Hello, how are you?",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "agent": "echo-agent",
  "message_count": 0,
  "echo_length": 18
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
Send a message to the agent

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
  "response": "Echo: Your message here",
  "session_id": "session-id",
  "agent": "echo-agent",
  "message_count": 2,
  "echo_length": 18
}
```

**Validation:**
- `message`: Required, max 10,000 characters
- `session_id`: Optional (auto-generated UUID if not provided), alphanumeric and hyphens only

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
├── EchoAgent (simple echo implementation)
├── create_agent() (factory function)
└── create_agent_from_env() (factory from environment)
```

### Core Components

**`Agent`**: Protocol defining the agent interface (duck-typed)
- `chat(message, history) -> AgentResponse`: Process messages
- `name`: Agent identifier

**`Message`**: Represents a conversation message with role and content

**`AgentResponse`**: Standardized response with content and metadata

**`EchoAgent`**: Simple implementation that echoes back user messages

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

# Create agent
agent = create_agent()

# Or from environment variables (same result for echo agent)
agent = create_agent_from_env()

# Chat with history
history = [
    Message("user", "First message"),
    Message("assistant", "Echo: First message")
]

response = agent.chat("Second message", history=history)
print(response.content)          # "Echo: Second message"
print(response.metadata)         # {"message_count": 2, "echo_length": 14}
```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `NGROK_AUTH_TOKEN` | ngrok authentication token | - | No* |
| `USE_NGROK` | Enable/disable ngrok tunnel | `true` | No |
| `DEBUG` | Enable Flask debug mode | `false` | No |

\* Without ngrok token, you get temporary URLs that change on restart

### Configuration Defaults

Defaults are defined in the code:

**Server Configuration** (in `agent.py`):
- `USE_NGROK` - Default: `true`
- `DEBUG` - Default: `false`
- `MAX_MESSAGE_LENGTH` - Default: `10000`

### Overriding Defaults

Override settings by setting environment variables:

```bash
export USE_NGROK=false
export DEBUG=true
```

## Running Without ngrok

To run without ngrok (local only):

```bash
export USE_NGROK=false
uv run agent.py
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
├── test_agents.py        # Test suite
├── pyproject.toml        # Project metadata and dependencies
└── README.md            # This file
```

### Running Tests

```bash
uv run pytest
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

1. **Add LLM Integration**: Replace EchoAgent with OpenAI, Anthropic, or other LLM providers
2. **Add Memory**: Integrate vector databases (Pinecone, Weaviate) for long-term memory
3. **Add Tools**: Implement function calling in your custom agent
4. **Add Auth**: Implement API key authentication for production use
5. **Add Database**: Store conversations in PostgreSQL/MongoDB instead of in-memory
6. **Add Streaming**: Implement streaming responses for better UX

### Custom Agent Example: LLM Integration

```python
from agents import AgentResponse
import os

class LLMAgent:
    """LLM-powered agent - implements Agent protocol"""

    def __init__(self, config=None):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = config.get("model", "gpt-4o") if config else "gpt-4o"

    def chat(self, message, history=None):
        messages = []
        if history:
            messages = [msg.to_dict() for msg in history]
        messages.append({"role": "user", "content": message})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )

        return AgentResponse(
            content=response.choices[0].message.content,
            metadata={
                "model": self.model,
                "tokens_used": response.usage.total_tokens
            }
        )

    @property
    def name(self):
        return f"llm-{self.model}"
```

### Custom Agent Example: Function Calling

```python
from agents import AgentResponse

class ToolAgent:
    """Agent with tool-calling capabilities - implements Agent protocol"""

    def __init__(self, config=None):
        self.config = config or {}
        self.tools = {
            "get_weather": self._get_weather,
        }

    def _get_weather(self, location: str) -> str:
        """Get weather for a location (stub implementation)"""
        return f"Weather in {location}: Sunny, 72°F"

    def chat(self, message, history=None):
        # Simple keyword detection for demo
        if "weather" in message.lower():
            location = "your location"  # Parse location from message
            result = self._get_weather(location)
            return AgentResponse(
                content=result,
                metadata={"tools_used": ["get_weather"]}
            )

        return AgentResponse(
            content=f"Processed: {message}",
            metadata={"tools_used": []}
        )

    @property
    def name(self):
        return "tool-agent"
```

## Troubleshooting

### ngrok Connection Issues

If ngrok fails to connect:
1. Check your auth token is correct
2. Verify you're not hitting ngrok's rate limits
3. Try running without ngrok: `export USE_NGROK=false`

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
2. **Rate Limiting**: Add rate limiting to prevent abuse (e.g., Flask-Limiter)
3. **Input Validation**: Already includes basic validation, but consider additional checks
4. **HTTPS Only**: Use ngrok's TLS endpoints or proper TLS certificates
5. **Secrets Management**: Use proper secrets management (e.g., AWS Secrets Manager, HashiCorp Vault)
6. **CORS**: Configure CORS properly if used with web frontends
7. **Memory Limits**: Implement conversation size limits or TTL-based expiration
8. **Thread Safety**: ✅ Implemented with threading.Lock for conversation storage
9. **Persistent Storage**: Consider replacing in-memory storage with Redis or a database for production

## Resources

- [uv Documentation](https://github.com/astral-sh/uv)
- [ngrok Documentation](https://ngrok.com/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [pyngrok Documentation](https://pyngrok.readthedocs.io/)
- [Python Protocols (PEP 544)](https://peps.python.org/pep-0544/)
- [PEP 585 Type Hints](https://peps.python.org/pep-0585/)

## License

This example is provided as-is for educational purposes.

## Next Steps

1. Implement custom agent with your own logic (LLM, rules-based, etc.)
2. Add function calling/tool use capabilities
3. Add persistent storage (database) for conversations
4. Create a web frontend for the chat interface
5. Add streaming responses for better UX
6. Implement RAG (retrieval-augmented generation)
7. Add observability (logging, metrics, tracing)
8. Deploy to production with proper authentication and rate limiting
