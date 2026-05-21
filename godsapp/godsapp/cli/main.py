"""GodsApp CLI — Click-based, shares backend with GUI."""
from __future__ import annotations

import asyncio
import json as _json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from godsapp import __version__
from godsapp.core import evidence as ev_svc
from godsapp.core import workspaces as ws_svc
from godsapp.core.health import check_health
from godsapp.core.jsonx import dumps
from godsapp.core.scans import ScanRequest, runner
from godsapp.db import init_db
from godsapp.tools import registry

console = Console()


@click.group(help="GodsApp — security auditing & research suite (CLI mode).")
@click.version_option(__version__, prog_name="godsapp")
def cli() -> None:
    init_db()
    registry.load_builtin()
    registry.load_plugins()


# ─── workspace ──────────────────────────────────────────────────────────────

@cli.group("workspace", help="Manage workspaces.")
def workspace_grp() -> None: ...


@workspace_grp.command("list")
def workspace_list() -> None:
    rows = ws_svc.list_workspaces()
    table = Table(title="Workspaces", show_lines=False)
    for col in ("id", "name", "target", "created"):
        table.add_column(col)
    for w in rows:
        table.add_row(w.id, w.name, w.target or "—", w.created_at.isoformat(timespec="seconds"))
    console.print(table)


@workspace_grp.command("create")
@click.argument("name")
@click.option("--target", default=None)
@click.option("--description", default=None)
def workspace_create(name: str, target: str | None, description: str | None) -> None:
    ws = ws_svc.create_workspace(name, description=description, target=target)
    console.print(f"[green]created[/] {ws.id}  {ws.name}")


@workspace_grp.command("delete")
@click.argument("workspace_id")
def workspace_delete(workspace_id: str) -> None:
    if ws_svc.delete_workspace(workspace_id):
        console.print(f"[red]deleted[/] {workspace_id}")
    else:
        console.print("[yellow]not found[/]")
        sys.exit(1)


# ─── tools ──────────────────────────────────────────────────────────────────

@cli.command("tools", help="List registered tools.")
def tools_cmd() -> None:
    by_cat = registry.by_category()
    for cat, items in by_cat.items():
        table = Table(title=cat.upper(), show_header=True, header_style="bold")
        table.add_column("name"); table.add_column("title")
        for t in items:
            table.add_row(t.name, t.title)
        console.print(table)


# ─── scan ───────────────────────────────────────────────────────────────────

@cli.group("scan", help="Run scans.")
def scan_grp() -> None: ...


@scan_grp.command("run")
@click.option("--workspace", "workspace_name", required=True, help="Workspace name.")
@click.option("--tool", "tool_name", required=True, help="Tool to run (see `godsapp-cli tools`).")
@click.option("--target", required=True)
@click.option("--arg", "args", multiple=True, help="key=value (repeatable)")
@click.option("--json", "as_json", is_flag=True, help="Emit a JSON summary at the end.")
def scan_run(workspace_name: str, tool_name: str, target: str,
             args: tuple[str, ...], as_json: bool) -> None:
    ws = next((w for w in ws_svc.list_workspaces() if w.name == workspace_name), None)
    if ws is None:
        console.print(f"[red]workspace not found: {workspace_name}[/]")
        sys.exit(2)
    parsed: dict[str, str] = {}
    for raw in args:
        if "=" not in raw:
            console.print(f"[red]bad --arg (need key=value): {raw}[/]")
            sys.exit(2)
        k, v = raw.split("=", 1)
        parsed[k.strip()] = v.strip()

    def on_out(scan_id, kind, text):
        if kind in ("stdout", "stderr"):
            sys.stdout.write(text); sys.stdout.flush()
        elif kind == "status":
            console.print(f"[dim]{text}[/]")

    runner.subscribe(on_out)
    scan = asyncio.run(runner.run(ScanRequest(
        workspace_id=ws.id, tool=tool_name, target=target, args=parsed)))

    if as_json:
        click.echo(dumps({
            "scan_id": scan.id,
            "status": scan.status,
            "exit_code": scan.exit_code,
            "findings": [
                {"title": f.title, "severity": f.severity, "host": f.host,
                 "port": f.port, "service": f.service}
                for f in scan.findings
            ],
        }, indent=2))
    else:
        console.print(f"[bold]{scan.status}[/] · exit {scan.exit_code} · {len(scan.findings)} findings")


# ─── evidence ───────────────────────────────────────────────────────────────

@cli.group("evidence", help="Evidence locker.")
def evidence_grp() -> None: ...


@evidence_grp.command("list")
def evidence_list() -> None:
    rows = ev_svc.list_evidence()
    table = Table(title="Evidence")
    for col in ("sha256[:12]", "filename", "size", "mime", "added"):
        table.add_column(col)
    for e in rows:
        table.add_row(e.sha256[:12], e.filename, f"{e.size_bytes:,}",
                      e.mime_type or "—",
                      e.created_at.isoformat(timespec="seconds"))
    console.print(table)


@evidence_grp.command("ingest")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--workspace", "workspace_name", default=None)
@click.option("--note", default=None)
def evidence_ingest(path: Path, workspace_name: str | None, note: str | None) -> None:
    ws_id = None
    if workspace_name:
        ws = next((w for w in ws_svc.list_workspaces() if w.name == workspace_name), None)
        if ws is None:
            console.print(f"[red]workspace not found: {workspace_name}[/]")
            sys.exit(2)
        ws_id = ws.id
    e = ev_svc.store_file(path, workspace_id=ws_id, note=note)
    console.print(f"[green]ingested[/] {e.sha256}  {e.filename}")


@evidence_grp.command("verify")
@click.argument("sha256")
def evidence_verify(sha256: str) -> None:
    rows = ev_svc.list_evidence()
    match = next((e for e in rows if e.sha256.startswith(sha256)), None)
    if match is None:
        console.print("[red]not found[/]")
        sys.exit(1)
    ok = ev_svc.verify(match)
    console.print(f"{match.filename}: {'[green]OK[/]' if ok else '[red]MISMATCH[/]'}")


# ─── api ────────────────────────────────────────────────────────────────────

@cli.group("api", help="Local REST API.")
def api_grp() -> None: ...


@api_grp.command("start")
@click.option("--host", default=None)
@click.option("--port", default=None, type=int)
def api_start(host: str | None, port: int | None) -> None:
    from godsapp.api.server import serve
    serve(host=host, port=port)


@api_grp.command("status")
def api_status() -> None:
    r = check_health()
    console.print({"db_ok": r.db_ok, "db_url": r.db_url, "api_running": r.api_running})


# ─── health ─────────────────────────────────────────────────────────────────

@cli.command("health", help="Show backend + tool availability snapshot.")
def health() -> None:
    r = check_health()
    click.echo(_json.dumps({
        "db_ok": r.db_ok,
        "db_url": r.db_url,
        "api_running": r.api_running,
        "tools": r.tools,
    }, indent=2))


# ─── updates ────────────────────────────────────────────────────────────────

@cli.group("update", help="In-app updater.")
def update_grp() -> None: ...


@update_grp.command("check", help="Check GitHub Releases for a newer version.")
@click.option("--include-prereleases", is_flag=True, default=None)
def update_check(include_prereleases: bool | None) -> None:
    from godsapp.core import updater as upd
    r = upd.check_for_update(allow_prerelease=include_prereleases)
    if r.error:
        console.print(f"[red]error:[/] {r.error}"); sys.exit(2)
    if r.info is None:
        console.print(f"[green]up to date[/] (v{r.current_version})"); return
    console.print(f"[yellow]update available:[/] v{r.info.version} "
                  f"(you have v{r.current_version})")
    console.print(f"  asset:  {r.info.asset_name}")
    console.print(f"  size:   {r.info.asset_size} bytes")
    console.print(f"  notes:\n{r.info.notes[:600]}")


@update_grp.command("install", help="Download and install the latest release.")
@click.option("--user", "user_scope", is_flag=True, help="Install under ~/.local (no pkexec).")
@click.option("--include-prereleases", is_flag=True, default=None)
def update_install(user_scope: bool, include_prereleases: bool | None) -> None:
    from godsapp.core import updater as upd
    r = upd.check_for_update(allow_prerelease=include_prereleases)
    if r.error:
        console.print(f"[red]error:[/] {r.error}"); sys.exit(2)
    if r.info is None:
        console.print(f"[green]already up to date[/] (v{r.current_version})"); return

    last_bytes = [-1]
    def _cb(p: upd._Progress) -> None:
        if p.bytes_total and p.bytes_done != last_bytes[0]:
            pct = 100 * p.bytes_done // max(1, p.bytes_total)
            console.print(f"  [{p.stage}] {pct}%", end="\r")
            last_bytes[0] = p.bytes_done
        else:
            console.print(f"  [{p.stage}] {p.message}")

    console.print(f"installing v{r.info.version} → {r.info.asset_name}")
    inst = upd.download_and_install(r.info, user_scope=user_scope, progress_cb=_cb)
    while inst.poll() is None:
        try:
            import time; time.sleep(0.5)
        except KeyboardInterrupt:
            inst.cancel(); console.print("[red]cancelled[/]"); sys.exit(130)
    rc = inst.poll() or 0
    if rc == 0:
        console.print(f"[green]install complete[/] — relaunch godsapp to use v{r.info.version}")
    else:
        console.print(f"[red]install failed (rc={rc})[/]")
        console.print(f"log: {inst.log_path}")
        sys.exit(rc)


if __name__ == "__main__":
    cli()
