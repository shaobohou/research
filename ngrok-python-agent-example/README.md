# ngrok Python Agent Example

A tiny Flask app plus a pluggable `Agent` interface that demonstrates how to expose a local webhook/chatbot over the public internet with ngrok. The default implementation is an `EchoAgent`, so you can focus on transport and structure before wiring in an LLM.

## Quick start
1. **Install deps**: `uv sync`
2. **Run the app**: `uv run agent.py`
3. **Send a request**:
   ```bash
   curl -X POST http://localhost:5000/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Hello"}'
   ```

## Configuration via flags
Environment variables are gone in favor of explicit [absl flags](https://abseil.io/docs/python/guides/flags). Pass them after `--` when invoking the script:

| Flag | Default | Purpose |
| --- | --- | --- |
| `--host` | `0.0.0.0` | Interface that Flask binds to. |
| `--port` | `5000` | Port for the development server (and your ngrok tunnel). |
| `--debug` | `False` | Enable Flask's debug server. |
| `--max_message_length` | `4000` | Guardrail for incoming payloads. |

Example:

```bash
uv run agent.py -- --port=6000 --max_message_length=1024 --debug
```

## Using the ngrok CLI
`pyngrok` support has been removed entirely—bring your own CLI tunnel:

1. Download the [ngrok CLI](https://ngrok.com/download) and authenticate: `ngrok config add-authtoken <token>`
2. Start the Flask server with whichever flags you need: `uv run agent.py`
3. In a separate terminal run: `ngrok http 5000`
4. Copy the forwarded URL from the CLI output and send it to your webhook provider.

Because the CLI owns the tunnel, the Python process has zero ngrok dependencies, making deployments (or container builds) lighter.

## HTTP surface area
The scaffold deliberately keeps the API tiny but still useful for webhook testing workflows:

- `GET /` – detailed health check that includes agent metadata, configured `max_message_length`, and a summary of the available routes.
- `POST /chat` – accepts `{ "message": str, "session_id": optional str }` and streams the request through the active agent while maintaining in-memory session history.
- `POST /webhook` – generic receiver that logs headers/payloads and replies with a basic acknowledgement, useful for validating ngrok tunnels with third-party webhook providers.
- `GET /conversations/<session_id>` – dumps the stored message history for the given session.
- `DELETE /conversations/<session_id>` – clears the server-side history for that session.

Swap the `EchoAgent` by implementing the `Agent` protocol in `agents.py` or by modifying `create_agent_from_env()`.

## Testing & linting
Run the usual project hygiene commands before pushing changes:

```bash
uv run ruff format .
uv run ruff check .
uv run pyright
uv run pytest
```

Pyright is configured directly in `pyproject.toml`, so editors/CI inherit the same include paths and settings. The existing unit tests cover the `Agent` protocol implementation and ensure the echo agent returns structured metadata for callers.
