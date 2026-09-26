# Home Assistant MCP

A Model Context Protocol server providing **limited, whitelisted access** to Home Assistant lights and switches.

## Tools

| Tool | Description |
|------|-------------|
| list_lights | List allowed lights with state |
| get_light | Get full details of a specific light |
| set_light | Turn a light on/off with brightness or color |
| list_switches | List allowed switches with state |
| get_switch | Get a specific switch state |
| set_switch | Turn a switch on/off |

## Setup

1. Clone the repo:
   git clone https://github.com/mgossman71/has-mcp
   cd has-mcp

2. Create your .env file:
   cp .env.example .env
   chmod 600 .env
   # Edit .env with your HA token and host

3. Configure the entity whitelist:
   cp config.example.yaml config.yaml
   # Edit config.yaml with your allowed entities

4. Start the server:
   docker compose up -d

The server will be available at http://localhost:8765/mcp

## .env File

Docker Compose reads .env automatically. Required variables:

| Variable | Description |
|----------|-------------|
| HA_TOKEN | Home Assistant long-lived access token (required) |
| HA_BASE_URL | Home Assistant URL e.g. http://192.168.1.100:8123 (required) |
| HA_ALLOWED_ENTITIES | Comma-separated override of config.yaml whitelist (optional) |

## Configuration

Edit config.yaml to set the entity whitelist. Supported domains: light.* and switch.*
Only whitelisted entities can be accessed - all others are rejected.

## MCP Client Registration

Point your MCP client at: http://localhost:8765/mcp

## Security

- Domain locked to light.* and switch.* only
- Entity whitelist enforced on every tool call
- No generic service-call tool exposed
- Token stored in .env (gitignored, chmod 600)
- config.yaml is gitignored
