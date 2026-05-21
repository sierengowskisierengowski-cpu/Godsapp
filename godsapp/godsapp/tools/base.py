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

    async def _run_subprocess(
        self,
        cmd: list[str],
        *,
        on_stdout: OutputCallback,
        on_stderr: OutputCallback,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> int:
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
