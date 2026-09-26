"""MCP server exposing limited Home Assistant controls (lights + switches)."""

from __future__ import annotations

import json
from typing import Any

import argparse

from mcp.server.mcpserver import MCPServer

from .client import HomeAssistantClient
from .config import load_config

mcp = MCPServer("homeassistant")

# Lazy-init: loaded on first tool call
_client: HomeAssistantClient | None = None
_config = None


def _get_client() -> HomeAssistantClient:
    global _client, _config
    if _client is None:
        _config = load_config()
        _client = HomeAssistantClient(_config)
    return _client


def _check_allowed(entity_id: str) -> str | None:
    """Return error string if entity is not allowed, else None."""
    if not _config.is_allowed(entity_id):
        return (
            f"Access denied: '{entity_id}' is not in the allowed entities list. "
            f"Allowed lights: {', '.join(sorted(_config.allowed_entities))}"
        )
    return None


@mcp.tool()
async def list_lights(on_only: bool = False) -> str:
    """List all allowed lights with their current state.

    Args:
        on_only: If true, only return lights that are currently on.
    """
    client = _get_client()
    states = await client.get_states("light")

    results = []
    for s in states:
        eid = s["entity_id"]
        if not _config.is_allowed(eid):
            continue
        if on_only and s["state"] != "on":
            continue

        name = s["attributes"].get("friendly_name", eid)
        entry = {
            "entity_id": eid,
            "name": name,
            "state": s["state"],
        }
        if s["state"] == "on":
            brightness = s["attributes"].get("brightness")
            if brightness is not None:
                entry["brightness_pct"] = round(brightness / 255 * 100)
        results.append(entry)

    return json.dumps(results, indent=2)


@mcp.tool()
async def get_light(entity_id: str) -> str:
    """Get the full state of a specific light.

    Args:
        entity_id: The light entity ID (e.g. 'light.garage').
    """
    error = _check_allowed(entity_id)
    if error:
        return json.dumps({"error": error})

    client = _get_client()
    state = await client.get_state(entity_id)

    result = {
        "entity_id": state["entity_id"],
        "name": state["attributes"].get("friendly_name", entity_id),
        "state": state["state"],
    }

    if state["state"] == "on":
        brightness = state["attributes"].get("brightness")
        if brightness is not None:
            result["brightness_pct"] = round(brightness / 255 * 100)
        rgb = state["attributes"].get("rgb_color")
        if rgb:
            result["rgb"] = rgb
        color_temp = state["attributes"].get("color_temp")
        if color_temp:
            result["color_temp_kelvin"] = color_temp

    return json.dumps(result, indent=2)


@mcp.tool()
async def set_light(
    entity_id: str,
    on: bool,
    brightness_pct: int | None = None,
    rgb: str | None = None,
) -> str:
    """Turn a light on or off, optionally setting brightness or color.

    Args:
        entity_id: The light entity ID (e.g. 'light.garage').
        on: True to turn on, False to turn off.
        brightness_pct: Brightness 0-100 (only used when on=True).
        rgb: Comma-separated RGB values e.g. '255,128,0' (only used when on=True).
    """
    error = _check_allowed(entity_id)
    if error:
        return json.dumps({"error": error})

    if brightness_pct is not None and not (0 <= brightness_pct <= 100):
        return json.dumps({"error": "brightness_pct must be between 0 and 100"})

    client = _get_client()
    data: dict[str, Any] = {"entity_id": entity_id}

    if on:
        if brightness_pct is not None:
            data["brightness"] = round(brightness_pct / 100 * 255)
        if rgb:
            try:
                parts = [int(x.strip()) for x in rgb.split(",")]
                if len(parts) != 3 or any(p < 0 or p > 255 for p in parts):
                    raise ValueError
                data["rgb_color"] = parts
            except ValueError:
                return json.dumps({"error": "rgb must be 3 comma-separated values 0-255"})

    await client.call_service("light", "turn_on" if on else "turn_off", data)

    return json.dumps({
        "entity_id": entity_id,
        "action": "turned on" if on else "turned off",
    })




@mcp.tool()
async def list_switches(on_only: bool = False) -> str:
    """List all allowed switches with their current state.

    Args:
        on_only: If true, only return switches that are currently on.
    """
    client = _get_client()
    states = await client.get_states("switch")

    results = []
    for s in states:
        eid = s["entity_id"]
        if not _config.is_allowed(eid):
            continue
        if on_only and s["state"] != "on":
            continue

        name = s["attributes"].get("friendly_name", eid)
        results.append({
            "entity_id": eid,
            "name": name,
            "state": s["state"],
        })

    return json.dumps(results, indent=2)


@mcp.tool()
async def get_switch(entity_id: str) -> str:
    """Get the state of a specific switch.

    Args:
        entity_id: The switch entity ID.
    """
    error = _check_allowed(entity_id)
    if error:
        return json.dumps({"error": error})

    client = _get_client()
    state = await client.get_state(entity_id)

    result = {
        "entity_id": state["entity_id"],
        "name": state["attributes"].get("friendly_name", entity_id),
        "state": state["state"],
    }

    return json.dumps(result, indent=2)


@mcp.tool()
async def set_switch(entity_id: str, on: bool) -> str:
    """Turn a switch on or off.

    Args:
        entity_id: The switch entity ID.
        on: True to turn on, False to turn off.
    """
    error = _check_allowed(entity_id)
    if error:
        return json.dumps({"error": error})

    client = _get_client()
    data = {"entity_id": entity_id}

    await client.call_service("switch", "turn_on" if on else "turn_off", data)

    return json.dumps({
        "entity_id": entity_id,
        "action": "turned on" if on else "turned off",
    })


def main():
    """Entry point for running the MCP server."""
    parser = argparse.ArgumentParser(description="Home Assistant Lights MCP Server")
    parser.add_argument("--http", action="store_true", help="Run with streamable HTTP transport")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host for HTTP mode")
    parser.add_argument("--port", type=int, default=8765, help="Bind port for HTTP mode")
    args = parser.parse_args()

    if args.http:
        import uvicorn
        app = mcp.streamable_http_app()
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()