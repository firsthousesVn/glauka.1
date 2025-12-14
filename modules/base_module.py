from __future__ import annotations

from typing import Protocol

from glauka.core.models import ReconContext


class BaseModule(Protocol):
    name: str
    enabled: bool
    depends_on: list[str]

    async def run(self, ctx: ReconContext) -> None:
        ...
