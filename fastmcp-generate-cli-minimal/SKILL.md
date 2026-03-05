---
name: "python-example-server-cli"
description: "CLI for the python example_server MCP server. Call tools, list resources, and get prompts."
---

# python example_server CLI

## Tool Commands

### add

Add two numbers together.

```bash
uv run test_cli.py add --a <value> --b <value>
```

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--a` | number | yes | First operand |
| `--b` | number | yes | Second operand |

### greet

Return a personalised greeting.

```bash
uv run test_cli.py greet --name <value> --loud --times <value>
```

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--name` | string | yes | Name to greet |
| `--loud` | boolean | no | Shout the greeting |
| `--times` | integer | no | How many times to repeat |

### join

Join a list of strings with a separator.

```bash
uv run test_cli.py join --words <value> --sep <value>
```

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--words` | array | yes | Words to join |
| `--sep` | string | no | Separator (default: space) |

### echo_json

Echo back a JSON object.

```bash
uv run test_cli.py echo_json --payload <value>
```

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--payload` | object | yes | Any JSON object (JSON string) |


## Utility Commands

```bash
uv run test_cli.py list-tools
uv run test_cli.py list-resources
uv run test_cli.py read-resource <uri>
uv run test_cli.py list-prompts
uv run test_cli.py call-tool <tool-name> [key=value ...]
```
