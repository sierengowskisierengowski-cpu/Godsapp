"""Tool base class — every built-in tool and plugin implements this."""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

OutputCallback = Callable[[str], None]


@dataclass
class ToolResult:
    exit_code: int
    findings: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolOption:
    """Declarative option spec used by the UI to render form controls."""
    key: str
    label: str
    kind: str = "text"          # text | int | bool | choice | password
    default: Any = None
    choices: Optional[list[str]] = None
    help: Optional[str] = None
    required: bool = False


class Tool(ABC):
    name: str = ""
    title: str = ""
    category: str = ""           # recon | web | network | password | exploit | ...
    description: str = ""
    requires_binary: Optional[str] = None
    options: list[ToolOption] = []
    # v0.4.0 — Learn Mode metadata
    difficulty: str = "intermediate"   # beginner | intermediate | expert
    learn_key: str = ""                # key into godsapp.core.learn.LEARN_CONTENT;
                                       # if blank, falls back to `name`

    @abstractmethod
    async def run(
        self,
        target: str,
        args: dict[str, Any],
        *,
        on_stdout: OutputCallback,
        on_stderr: OutputCallback,
    ) -> ToolResult: ...

    def _resolve_binary(self, name: str) -> str:
        """If the user has pinned an override path (Settings → Tool Paths)
        for `self.requires_binary` — or for any alias known to the catalog —
        rewrite ``name`` to the override's absolute path. Falls back to the
        original name (relying on ``$PATH`` lookup) on any miss so the
        legacy execution flow keeps working.
        """
        if not name:
            return name
        try:
            from godsapp.core.settings import load_settings
            from godsapp.core.tool_catalog import CATALOG
            overrides = load_settings().tool_paths.overrides
            if not overrides:
                return name
            # Direct match on the tool's declared requires_binary.
            if self.requires_binary and self.requires_binary in overrides:
                entry = CATALOG.get(self.requires_binary)
                if entry and name in entry.binaries:
                    return overrides[self.requires_binary]
                if name == self.requires_binary:
                    return overrides[self.requires_binary]
            # Fallback: any catalog entry whose binaries tuple contains
            # ``name`` and which has an override set.
            for tool_id, entry in CATALOG.items():
                if name in entry.binaries and tool_id in overrides:
                    return overrides[tool_id]
        except Exception:
            pass
        return name

    async def _run_subprocess(
        self,
        cmd: list[str],
        *,
        on_stdout: OutputCallback,
        on_stderr: OutputCallback,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> int:
        if cmd:
            cmd = [self._resolve_binary(cmd[0]), *cmd[1:]]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
        )

        async def _pump(stream: Optional[asyncio.StreamReader], cb: OutputCallback) -> None:
            if stream is None:
                return
            while True:
                line = await stream.readline()
                if not line:
                    break
                cb(line.decode(errors="replace"))

        await asyncio.gather(_pump(proc.stdout, on_stdout), _pump(proc.stderr, on_stderr))
        return await proc.wait()
