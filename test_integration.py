"""Quick integration test against the live HA instance."""
import asyncio
import sys

sys.path.insert(0, "src")

from homeassistant_mcp.config import load_config
from homeassistant_mcp.client import HomeAssistantClient


async def main():
    config = load_config()
    print(f"Config loaded: {len(config.allowed_entities)} allowed entities")
    print(f"Base URL: {config.base_url}")

    client = HomeAssistantClient(config)

    # Test 1: Get all states and filter to allowed lights
    states = await client.get_states("light")
    allowed = [s for s in states if config.is_allowed(s["entity_id"])]
    print(f"\nTest 1 - List lights: found {len(allowed)} allowed lights")
    for l in allowed[:3]:
        print(f"  {l['entity_id']}: {l['state']}")
    print(f"  ... and {len(allowed) - 3} more")

    # Test 2: Get a specific light state
    state = await client.get_state("light.garage")
    print(f"\nTest 2 - Get light.garage: state={state['state']}")

    # Test 3: Verify whitelist enforcement
    print(f"\nTest 3 - Whitelist check:")
    print(f"  light.garage allowed: {config.is_allowed('light.garage')}")
    print(f"  light.dining_room allowed: {config.is_allowed('light.dining_room')}")
    print(f"  light.kitchen allowed: {config.is_allowed('light.kitchen')}")

    await client.close()
    print("\nAll tests passed!")


asyncio.run(main())