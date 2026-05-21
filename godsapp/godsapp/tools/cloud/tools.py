"""Cloud tools — AWS CLI identity + IAM enumeration, gcloud auth probe."""
from __future__ import annotations

import json
import shutil
from typing import Any

from godsapp.tools.base import Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


class AwsStsTool(Tool):
    name = "aws-sts"
    title = "AWS — identity + IAM probe"
    category = "cloud"
    description = "Whoami via STS, plus optional enumeration of attached user/group IAM policies."
    requires_binary = "aws"
    options = [
        ToolOption("profile", "AWS profile (blank = default)", "text", default=""),
        ToolOption("region", "Region", "text", default="us-east-1"),
        ToolOption("enumerate_iam", "Enumerate IAM user policies", "bool", default=True),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("aws") is None:
            on_stderr("aws cli not installed (pip install awscli)\n")
            return ToolResult(exit_code=127)
        prof = []
        if args.get("profile"):
            prof = ["--profile", str(args["profile"])]
        region = ["--region", str(args.get("region") or "us-east-1")]
        cmd = ["aws", "sts", "get-caller-identity", "--output", "json"] + prof + region
        on_stdout(f"$ {' '.join(cmd)}\n")
        buf: list[str] = []
        def cb(line: str) -> None:
            buf.append(line); on_stdout(line)
        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        findings: list[dict[str, Any]] = []
        user_name = None
        if rc == 0:
            try:
                ident = json.loads("".join(buf))
                arn = ident.get("Arn", "")
                findings.append({"title": f"caller {arn}", "severity": "info",
                                 "data": ident})
                if ":user/" in arn:
                    user_name = arn.split(":user/", 1)[1]
            except Exception as e:
                on_stderr(f"json: {e}\n")

        if rc == 0 and args.get("enumerate_iam") and user_name:
            for sub in (
                ["aws", "iam", "list-attached-user-policies", "--user-name", user_name, "--output", "json"],
                ["aws", "iam", "list-user-policies", "--user-name", user_name, "--output", "json"],
                ["aws", "iam", "list-groups-for-user", "--user-name", user_name, "--output", "json"],
            ):
                buf2: list[str] = []
                def cb2(line: str) -> None:
                    buf2.append(line); on_stdout(line)
                sub_cmd = sub + prof + region
                on_stdout(f"$ {' '.join(sub_cmd)}\n")
                rc2 = await self._run_subprocess(sub_cmd, on_stdout=cb2, on_stderr=on_stderr)
                if rc2 == 0:
                    try:
                        data = json.loads("".join(buf2))
                        for key, items in data.items():
                            if isinstance(items, list):
                                for it in items:
                                    name = it.get("PolicyName") or it.get("GroupName") or json.dumps(it)[:80]
                                    findings.append({
                                        "title": f"{key} → {name}",
                                        "severity": "low",
                                        "data": it if isinstance(it, dict) else {"raw": it},
                                    })
                    except Exception as e:
                        on_stderr(f"json: {e}\n")
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd, "user": user_name})


class GcloudInfoTool(Tool):
    name = "gcloud-info"
    title = "gcloud — auth + project probe"
    category = "cloud"
    description = "List active gcloud accounts and projects."
    requires_binary = "gcloud"
    options = []

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("gcloud") is None:
            on_stderr("gcloud not installed (Google Cloud SDK)\n")
            return ToolResult(exit_code=127)
        findings: list[dict[str, Any]] = []
        rc_total = 0
        for label, cmd in (
            ("auth", ["gcloud", "auth", "list", "--format=json"]),
            ("projects", ["gcloud", "projects", "list", "--format=json"]),
            ("config", ["gcloud", "config", "list", "--format=json"]),
        ):
            on_stdout(f"$ {' '.join(cmd)}\n")
            buf: list[str] = []
            def cb(line: str) -> None:
                buf.append(line); on_stdout(line)
            rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
            rc_total |= rc
            try:
                payload = json.loads("".join(buf) or "null")
            except Exception:
                payload = None
            if isinstance(payload, list):
                for item in payload:
                    title = (item.get("account") or item.get("projectId") or
                             item.get("name") or json.dumps(item)[:80])
                    findings.append({"title": f"{label}: {title}", "severity": "info",
                                     "data": item})
            elif isinstance(payload, dict):
                findings.append({"title": f"{label}", "severity": "info", "data": payload})
        return ToolResult(exit_code=rc_total, findings=findings, meta={})


registry.register(AwsStsTool())
registry.register(GcloudInfoTool())
