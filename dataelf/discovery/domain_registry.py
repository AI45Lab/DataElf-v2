from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class DomainRegistry:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).resolve().parents[1] / "domains"

    def load_domain_pack(self, domain: str) -> dict[str, Any]:
        path = self.root / domain / "domain.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Domain pack not found: {path}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if payload.get("domain") != domain:
            raise ValueError(f"Domain pack {path} has unexpected domain: {payload.get('domain')}")
        return payload

