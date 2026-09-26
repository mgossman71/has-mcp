# Home Assistant MCP

A [Model Context Protocol](https://modelcontextprotocol.io/) server providing **limited, whitelisted access** to Home Assistant lights and switches.

## Tools

| Tool | Description |
|------|-------------|
| list_lights | List allowed lights with state |
| get_light | Get full details of a specific light |
| set_light | Turn a light on/off with brightness or color |
| list_switches | List allowed switches with state |
| get_switch | Get a specific switch state |
| set_switch | Turn a switch on/off |

## Running with Docker Compose

1. Copy and edit config:
   cp config.example.yaml config.yaml
2. Set your token:
   export HA_TOKEN=your-token
3. Build and start:
   docker compose up -d

The server listens on http://localhost:8765/mcp (streamable HTTP).

### Environment variables

| Variable | Description |
|----------|-------------|
| HA_TOKEN | Home Assistant access token (required) |
| HA_BASE_URL | HA URL (overrides config.yaml) |
| HA_ALLOWED_ENTITIES | Comma-separated override |

## Running locally

python3.11 -m venv .venv && source .venv/bin/activate && pip install -e .
export HA_TOKEN=your-token
python -m homeassistant_mcp.server --http  # HTTP mode
python -m homeassistant_mcp.server         # stdio mode

## Configuration

Copy config.example.yaml to config.yaml and edit the allowed_entities list.
Supported domains: light.* and switch.*
Only whitelisted entities can be accessed. All others are rejected.

## MCP Client Registration

HTTP: point your client at http://localhost:8765/mcp
stdio: use docker run --rm -e HA_TOKEN=... has-mcp

## Security

- Domain locked to light.* and switch.* only
- Entity whitelist enforced on every tool call
- No generic service-call tool exposed
- Token from env var, never in code
- config.yaml is git-ignored
