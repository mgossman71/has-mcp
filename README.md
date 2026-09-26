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

## Discovering entities to whitelist

Not sure which entity IDs to add to `allowed_entities`? A scanner is included for
exactly that.

- **Source code:** `src/homeassistant_mcp/scan.py`
- **Command:** `homeassistant-mcp-scan` (declared in `pyproject.toml`)

It reads `HA_BASE_URL` and `HA_TOKEN` from your `.env` (or the environment), lists
every light/switch your server exposes, and marks which are already whitelisted.

### Run it locally (simplest - no Docker)

From the project root (the directory that contains your `.env`):

1. Create and activate a virtual environment:

       python3 -m venv .venv
       source .venv/bin/activate          # Windows: .venv\Scripts\activate

2. Install the package - this is what puts `homeassistant-mcp-scan` on your PATH:

       pip install -e .

3. Run it:

       homeassistant-mcp-scan            # list all light/switch entities
       homeassistant-mcp-scan --new-only # only ones not yet in config.yaml
       homeassistant-mcp-scan --write    # append the new ones to config.yaml
       homeassistant-mcp-scan --all      # include every domain, not just light/switch

If `pip install` complains about an "externally-managed-environment", you skipped
step 1 - activate the venv and retry. If `python3 -m venv` itself fails (missing
`ensurepip`), install it first: `sudo apt install -y python3-venv` (Debian/Ubuntu),
then retry. Without a venv you can also run the module directly once the deps are
installed: `python3 -m homeassistant_mcp.scan --new-only`.

### Run it with Docker (no local Python needed)

Rebuild so the image includes the new command, then run it inside the container
(it uses the same `.env`):

    docker compose build
    docker compose run --rm homeassistant-mcp homeassistant-mcp-scan --new-only

Note: in Docker, `config.yaml` is baked into the image at build time, so `--write`
does not persist. For that path, copy the printed YAML into your local `config.yaml`
and rebuild.

### Example output

    Scanned http://10.0.0.25:8123 - 24 light, 6 switch

    Lights
      [ok]  light.garage        Garage
      [new] light.dining_room   Dining Room

    Switches
      [new] switch.shelly1pm    Shelly 1 PM

    ------------------------------------------------------------
    Paste into config.yaml (allowed_entities):
    allowed_entities:
      - light.dining_room
      - light.garage
      ...

    Or override via .env (HA_ALLOWED_ENTITIES):
    HA_ALLOWED_ENTITIES=light.dining_room,light.garage,...

## MCP Client Registration

Point your MCP client at: http://localhost:8765/mcp

## Security

- Domain locked to light.* and switch.* only
- Entity whitelist enforced on every tool call
- No generic service-call tool exposed
- Token stored in .env (gitignored, chmod 600)
- config.yaml is gitignored
