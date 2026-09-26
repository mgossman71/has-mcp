"""Scan a Home Assistant server for entities you can add to the MCP whitelist.

Reads HA_BASE_URL and HA_TOKEN from environment variables (falling back to the
.env file), lists the light/switch entities the server exposes, cross-references
them with the current config.yaml whitelist, and prints copy-paste-ready blocks
for config.yaml / HA_ALLOWED_ENTITIES.

Usage:
    homeassistant-mcp-scan                 # list all light/switch entities
    homeassistant-mcp-scan --new-only      # only ones not yet whitelisted
    homeassistant-mcp-scan --write         # append new ones to config.yaml
    homeassistant-mcp-scan --all           # include every domain, not just light/switch
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

import aiohttp
import yaml

from .client import HomeAssistantClient
from .config import Config

SUPPORTED_DOMAINS = ("light", "switch")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Credentials / config discovery
# ---------------------------------------------------------------------------
def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file without any external dependency."""
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip a single pair of surrounding quotes, if present.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_credentials(env_path: str | None = None) -> tuple[str, str]:
    """Resolve HA_BASE_URL and HA_TOKEN.

    Environment variables take precedence; the .env file fills any gaps so the
    command works both locally (where Python does not read .env automatically)
    and inside Docker (where the values arrive as real env vars).
    """
    base_url = os.environ.get("HA_BASE_URL", "").rstrip("/")
    token = os.environ.get("HA_TOKEN", "")

    path = Path(env_path) if env_path else PROJECT_ROOT / ".env"
    if env_path and not path.is_file():
        raise FileNotFoundError(f".env file not found: {path}")

    values = parse_env_file(path) if path.is_file() else {}

    if not base_url:
        base_url = values.get("HA_BASE_URL", "").rstrip("/")
    if not token:
        token = values.get("HA_TOKEN", "")

    missing = [k for k, v in (("HA_BASE_URL", base_url), ("HA_TOKEN", token)) if not v]
    if missing:
        raise ValueError(
            f"Missing {' and '.join(missing)}. Set them in .env (see .env.example) "
            f"or export them as environment variables."
        )
    return base_url, token


def _find_config_file(config_path: str | None = None) -> Path | None:
    """Locate config.yaml, mirroring the search order in config.py. None if absent."""
    if config_path:
        p = Path(config_path)
        return p if p.is_file() else None

    env_path = os.environ.get("HA_MCP_CONFIG")
    if env_path and Path(env_path).is_file():
        return Path(env_path)

    for candidate in (Path("/app/config.yaml"), PROJECT_ROOT / "config.yaml", Path.cwd() / "config.yaml"):
        if candidate.is_file():
            return candidate
    return None


def load_existing_whitelist(config_path: str | None = None) -> set[str]:
    """Best-effort read of the current allowed_entities from config.yaml."""
    path = _find_config_file(config_path)
    if path is None:
        return set()
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except Exception:
        return set()
    entities = raw.get("allowed_entities", []) or []
    return {e for e in entities if isinstance(e, str)}


# ---------------------------------------------------------------------------
# Scanning + rendering
# ---------------------------------------------------------------------------
def _domain(entity_id: str) -> str:
    return entity_id.split(".", 1)[0] if "." in entity_id else ""


def _plural(domain: str) -> str:
    """Human-friendly section label for a domain (light -> Lights, etc.)."""
    if domain == "switch":
        return "Switches"
    return domain.capitalize() + "s"


async def run_scan(config: Config) -> list[dict]:
    """Fetch every entity's state from Home Assistant."""
    client = HomeAssistantClient(config)
    try:
        # get_states() ignores its argument and returns all entity states.
        return await client.get_states("*")
    finally:
        await client.close()


def _filtered(states: list[dict], include_all: bool) -> list[dict]:
    if include_all:
        return states
    return [s for s in states if _domain(s["entity_id"]) in SUPPORTED_DOMAINS]


def _render(base_url: str, states: list[dict], existing: set[str], new_only: bool) -> list[str]:
    """Render the human-readable report (light/switch only)."""
    grouped: dict[str, list[dict]] = {}
    for s in _filtered(states, include_all=False):
        grouped.setdefault(_domain(s["entity_id"]), []).append(s)

    domain_order = [d for d in SUPPORTED_DOMAINS if d in grouped]
    domain_order += sorted(d for d in grouped if d not in SUPPORTED_DOMAINS)

    lines: list[str] = []
    if not domain_order:
        lines.append(f"Scanned {base_url} - no light/switch entities found.")
        return lines

    counts = ", ".join(f"{len(grouped[d])} {d}" for d in domain_order)
    lines.append(f"Scanned {base_url} - {counts}")
    lines.append("")

    for d in domain_order:
        items = sorted(grouped[d], key=lambda s: s["entity_id"])
        if new_only:
            items = [s for s in items if s["entity_id"] not in existing]
        if not items:
            continue
        width = max(len(s["entity_id"]) for s in items)
        lines.append(_plural(d))
        for s in items:
            eid = s["entity_id"]
            name = s.get("attributes", {}).get("friendly_name", eid)
            marker = "[ok]" if eid in existing else "[new]"
            lines.append(f"  {marker} {eid:<{width}}  {name}")
        lines.append("")

    return lines


def _copy_paste_blocks(states: list[dict], existing: set[str], include_all: bool, new_only: bool):
    """Return (list-of-lines, entity-ids) for the copy-paste output sections."""
    filtered = _filtered(states, include_all)
    if new_only:
        filtered = [s for s in filtered if s["entity_id"] not in existing]
    entities = sorted(s["entity_id"] for s in filtered)

    lines = []
    lines.append("Paste into config.yaml (allowed_entities):")
    lines.append("allowed_entities:")
    for e in entities:
        lines.append(f"  - {e}")
    lines.append("")
    lines.append("Or override via .env (HA_ALLOWED_ENTITIES):")
    lines.append("HA_ALLOWED_ENTITIES=" + ",".join(entities))
    return lines, entities


def append_to_config(config_path: Path, new_entities: list[str]) -> None:
    """Append entities to the allowed_entities block, preserving comments."""
    lines = config_path.read_text().splitlines(keepends=True)
    new_lines = [f"  - {e}\n" for e in new_entities]

    block_idx = next(
        (i for i, l in enumerate(lines) if re.match(r"^allowed_entities:\s*$", l)), None
    )
    inline_idx = next(
        (i for i, l in enumerate(lines) if re.match(r"^allowed_entities:\s*\[\]\s*$", l)), None
    )

    if block_idx is not None:
        # Insert at the end of the (possibly comment-interleaved) indented block.
        end = block_idx + 1
        while end < len(lines):
            if lines[end].strip() == "" or lines[end].startswith((" ", "\t")):
                end += 1
                continue
            break
        lines[end:end] = new_lines
    elif inline_idx is not None:
        lines[inline_idx] = "allowed_entities:\n"
        lines[inline_idx + 1: inline_idx + 1] = new_lines
    else:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        if lines and lines[-1].strip() != "":
            lines.append("\n")
        lines.append("allowed_entities:\n")
        lines.extend(new_lines)

    config_path.write_text("".join(lines))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="homeassistant-mcp-scan",
        description="Scan Home Assistant for entities you can add to the MCP whitelist.",
    )
    parser.add_argument("--config", help="Path to config.yaml (default: auto-detected)")
    parser.add_argument("--env", help="Path to .env file (default: project-root .env)")
    parser.add_argument(
        "--all", action="store_true", help="Include all domains, not just light/switch"
    )
    parser.add_argument(
        "--new-only", action="store_true", help="Only show entities not already whitelisted"
    )
    parser.add_argument(
        "--write", action="store_true", help="Append new light/switch entities to config.yaml"
    )
    args = parser.parse_args()

    try:
        base_url, token = load_credentials(args.env)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    existing = load_existing_whitelist(args.config)
    if existing:
        print(f"Current whitelist: {len(existing)} entities (from config.yaml)")
        print("")

    config = Config(base_url=base_url, token=token, allowed_entities=frozenset())
    try:
        states = asyncio.run(run_scan(config))
    except aiohttp.ClientResponseError as exc:
        if exc.status == 401:
            print(
                f"Error: invalid token (401) from {base_url}. Check HA_TOKEN in .env.",
                file=sys.stderr,
            )
        else:
            print(f"Error: Home Assistant returned HTTP {exc.status}.", file=sys.stderr)
        sys.exit(1)
    except aiohttp.ClientError as exc:
        print(
            f"Error: could not reach Home Assistant at {base_url}: {exc}", file=sys.stderr
        )
        sys.exit(1)

    for line in _render(base_url, states, existing, args.new_only):
        print(line)

    blocks, entities = _copy_paste_blocks(states, existing, args.all, args.new_only)
    if entities:
        print("-" * 60)
        for line in blocks:
            print(line)

    if args.write:
        supported = [e for e in entities if _domain(e) in SUPPORTED_DOMAINS]
        new = sorted(e for e in supported if e not in existing)
        skipped = [e for e in entities if _domain(e) not in SUPPORTED_DOMAINS]
        if new:
            cfg_path = _find_config_file(args.config)
            if cfg_path is None:
                print("\nError: no config.yaml found to write to.", file=sys.stderr)
                sys.exit(1)
            append_to_config(cfg_path, new)
            noun = "entity" if len(new) == 1 else "entities"
            print(f"\nAppended {len(new)} new {noun} to {cfg_path}")
        else:
            print("\nNothing to write - all found light/switch entities are already whitelisted.")
        if skipped:
            print(
                f"\nNote: skipped {len(skipped)} non-supported entities "
                f"(only light/switch can be whitelisted)."
            )


if __name__ == "__main__":
    main()