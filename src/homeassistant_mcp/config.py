"""Configuration loading and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    """Validated MCP server configuration."""

    base_url: str
    token: str
    allowed_entities: frozenset[str]

    def is_allowed(self, entity_id: str) -> bool:
        """Check if an entity is in the whitelist."""
        return entity_id in self.allowed_entities


def _find_config_path() -> Path:
    """Find config.yaml: env var > /app (docker) > project root > cwd."""
    env_path = os.environ.get("HA_MCP_CONFIG")
    if env_path:
        p = Path(env_path)
        if not p.is_file():
            raise FileNotFoundError(f"Config file not found: {p}")
        return p

    # Docker: config baked into /app
    candidate = Path("/app/config.yaml")
    if candidate.is_file():
        return candidate

    # Look in project root (parent of src/)
    project_root = Path(__file__).resolve().parent.parent.parent
    candidate = project_root / "config.yaml"
    if candidate.is_file():
        return candidate

    # Fall back to cwd
    candidate = Path.cwd() / "config.yaml"
    if candidate.is_file():
        return candidate

    # No config file — will try env vars only
    return None


def load_config() -> Config:
    """Load and validate configuration from YAML file."""
    path = _find_config_path()

    if path is not None:
        raw = yaml.safe_load(path.read_text())
        base_url = (raw.get("base_url") or "").rstrip("/")
        token = raw.get("token", "")
        entities = raw.get("allowed_entities", [])
    else:
        raw = {}
        base_url = ""
        token = ""
        entities = []

    # Env vars take precedence / fill in gaps
    base_url = os.environ.get("HA_BASE_URL", base_url).rstrip("/")
    token = os.environ.get("HA_TOKEN", token)

    env_entities = os.environ.get("HA_ALLOWED_ENTITIES", "")
    if env_entities:
        entities = [e.strip() for e in env_entities.split(",") if e.strip()]

    if not base_url:
        raise ValueError(
            "No base URL configured. Set HA_BASE_URL env var or 'base_url' in config.yaml."
        )
    if not token:
        raise ValueError(
            "No token found. Set the HA_TOKEN environment variable or "
            "add 'token' to config.yaml."
        )
    if not entities:
        raise ValueError(
            "No allowed entities. Set HA_ALLOWED_ENTITIES env var or "
            "'allowed_entities' in config.yaml."
        )

    # Validate all entities are supported domains
    for e in entities:
        if not (e.startswith("light.") or e.startswith("switch.")):
            raise ValueError(
                f"Entity '{e}' is not supported. Only 'light.*' and 'switch.*' entities are allowed."
            )

    return Config(
        base_url=base_url,
        token=token,
        allowed_entities=frozenset(entities),
    )