from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RegistryServer:
    id: str
    url: str
    enabled: bool = True
    rate_limit_per_minute: int = 60
    profile: Optional[str] = None
