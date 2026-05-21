# Contributing to GodsApp

## Dev setup

```bash
git clone https://github.com/jsierengowski/godsapp
cd godsapp
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[dev,postgres]"
godsapp                 # launch GUI from source
godsapp-cli --help
```

The `--system-site-packages` flag lets the venv see the distro-installed
PyGObject + GTK4 + libadwaita bindings.

## Project layout

See `README.md` for the directory map. Quick pointers:

- `godsapp/tools/<category>/<tool>.py` — built-in tool implementations
- `godsapp/ui/views/scan_view.py` — generic per-tool UI (auto-renders form from `tool.options`)
- `godsapp/db/models.py` — single source of truth for the schema
- `godsapp/core/scans.py` — async scan runner with live output streaming

## Adding a built-in tool

1. Subclass `godsapp.tools.base.Tool` in `godsapp/tools/<category>/<name>.py`.
2. Set `name`, `title`, `category`, `description`, `requires_binary` (optional), `options`.
3. Implement `async def run(...) -> ToolResult`. Use `self._run_subprocess(...)` for shelling out.
4. Call `registry.register(MyTool())` at module level.
5. Import the new module from `godsapp/tools/<category>/__init__.py` so the registry walk picks it up.

The UI and CLI pick up the new tool automatically — no further wiring required.

## Writing an external plugin

Place a Python package at `~/.local/share/godsapp/plugins/<name>/`. Its
`__init__.py` follows the same pattern as a built-in tool. The plugin
loader runs at startup and any registration errors surface in the log.

## Style

- Python 3.12+, full type hints, `from __future__ import annotations`.
- No `console.log` analogue — use the `logging` module via `godsapp.core.logging.get_logger`.
- Always pass `default=str` to `json.dumps` (use `godsapp.core.jsonx.dumps`).
- Never `pass` an exception silently — log it.

## Release checklist

1. Bump `__version__` in `godsapp/__init__.py` and `version` in `pyproject.toml`.
2. Update `packaging/debian/changelog` and `packaging/arch/PKGBUILD`.
3. `python -m build` → upload wheel + sdist.
4. Tag `v0.x.y` and push.
