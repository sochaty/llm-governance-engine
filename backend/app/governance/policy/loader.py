from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml

from typing import Optional, Union

from .schema import GovernancePolicy

logger = logging.getLogger(__name__)

# Resolved at import time so tests can override via env var before importing.
_DEFAULT_POLICY_PATH = os.getenv("GOVERNANCE_POLICY_PATH", "policies/default.yaml")


class PolicyLoader:
    """Loads GovernancePolicy from a YAML file on disk."""

    def load(self, path: Optional[Union[str, Path]] = None) -> GovernancePolicy:
        policy_path = Path(path) if path else Path(_DEFAULT_POLICY_PATH)

        if not policy_path.exists():
            logger.warning(
                "Policy file not found at '%s'. Using empty policy (all requests pass).",
                policy_path,
            )
            return GovernancePolicy()

        try:
            with open(policy_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                return GovernancePolicy()

            policy = GovernancePolicy(**data)
            logger.info(
                "Loaded %d governance rules from '%s'.", len(policy.rules), policy_path
            )
            return policy

        except yaml.YAMLError as exc:
            logger.error("YAML parse error in '%s': %s", policy_path, exc)
            return GovernancePolicy()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load policy from '%s': %s", policy_path, exc)
            return GovernancePolicy()

    def load_from_string(self, content: str) -> GovernancePolicy:
        data = yaml.safe_load(content) or {}
        return GovernancePolicy(**data)
