"""Crypto & Encoding tools — openssl hash, openssl cipher, multi-base codec.

The codec tool is pure-Python and always available (no `requires_binary`).
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import shutil
from pathlib import Path
from typing import Any

from godsapp.tools.base import Tool, ToolOption, ToolResult
from godsapp.tools.registry import registry


_HASH_ALGOS = ["md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3-256", "sha3-512", "blake2b", "blake2s"]


class OpensslHashTool(Tool):
    name = "openssl-hash"
    title = "OpenSSL — file hash"
    category = "crypto"
    description = "Compute a cryptographic digest of a file using OpenSSL. Target = file path."
    requires_binary = "openssl"
    options = [
        ToolOption("algorithm", "Algorithm", "choice", default="sha256", choices=_HASH_ALGOS),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("openssl") is None:
            on_stderr("openssl not installed\n")
            return ToolResult(exit_code=127)
        algo = str(args.get("algorithm") or "sha256")
        cmd = ["openssl", "dgst", f"-{algo}", target]
        on_stdout(f"$ {' '.join(cmd)}\n")
        digest_holder: list[str] = []
        def cb(line: str) -> None:
            on_stdout(line)
            if "= " in line:
                digest_holder.append(line.split("= ", 1)[1].strip())
        rc = await self._run_subprocess(cmd, on_stdout=cb, on_stderr=on_stderr)
        findings: list[dict[str, Any]] = []
        if digest_holder:
            findings.append({"title": f"{algo}({Path(target).name}) = {digest_holder[0]}",
                             "severity": "info", "data": {"algorithm": algo, "digest": digest_holder[0]}})
        return ToolResult(exit_code=rc, findings=findings, meta={"command": cmd})


class OpensslCipherTool(Tool):
    name = "openssl-cipher"
    title = "OpenSSL — symmetric encrypt / decrypt"
    category = "crypto"
    description = "Encrypt or decrypt a file with OpenSSL using a passphrase-derived key (PBKDF2)."
    requires_binary = "openssl"
    options = [
        ToolOption("mode", "Mode", "choice", default="encrypt", choices=["encrypt", "decrypt"]),
        ToolOption("cipher", "Cipher", "choice", default="aes-256-cbc",
                   choices=["aes-128-cbc", "aes-256-cbc", "aes-256-ctr", "aes-256-gcm", "chacha20"]),
        ToolOption("passphrase", "Passphrase", "password", default="", required=True),
        ToolOption("output", "Output file path", "text", default="", required=True),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        if shutil.which("openssl") is None:
            on_stderr("openssl not installed\n")
            return ToolResult(exit_code=127)
        passphrase = str(args.get("passphrase") or "")
        output = str(args.get("output") or "")
        if not passphrase or not output:
            on_stderr("passphrase and output path are required\n")
            return ToolResult(exit_code=2)
        cmd = ["openssl", "enc", f"-{args.get('cipher') or 'aes-256-cbc'}",
               "-pbkdf2", "-salt", "-pass", "stdin",
               "-in", target, "-out", output]
        if (args.get("mode") or "encrypt") == "decrypt":
            cmd.append("-d")
        on_stdout(f"$ {' '.join(c if c != passphrase else '***' for c in cmd)}\n")
        # Pipe passphrase via stdin
        import asyncio
        proc = await asyncio.create_subprocess_exec(*cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate((passphrase + "\n").encode())
        if stdout:
            on_stdout(stdout.decode(errors="replace"))
        if stderr:
            on_stderr(stderr.decode(errors="replace"))
        rc = proc.returncode or 0
        findings: list[dict[str, Any]] = []
        if rc == 0:
            findings.append({"title": f"{(args.get('mode') or 'encrypt')}ed → {output}",
                             "severity": "info", "data": {"output": output, "cipher": args.get("cipher")}})
        return ToolResult(exit_code=rc, findings=findings,
                          artifacts=[output] if rc == 0 else [], meta={"command": cmd})


class CodecTool(Tool):
    """Pure-Python encoder/decoder — no external binary required."""
    name = "codec"
    title = "Codec — base64 / hex / url / rot13 encode/decode"
    category = "crypto"
    description = "Encode or decode text in common formats. Target = the input string."
    requires_binary = None
    options = [
        ToolOption("operation", "Operation", "choice", default="encode", choices=["encode", "decode"]),
        ToolOption("format", "Format", "choice", default="base64",
                   choices=["base64", "base32", "base16-hex", "url", "rot13", "ascii85"]),
    ]

    async def run(self, target, args, *, on_stdout, on_stderr):
        op = args.get("operation") or "encode"
        fmt = args.get("format") or "base64"
        on_stdout(f"$ codec {op} {fmt} (len={len(target)})\n")
        try:
            data = target.encode() if op == "encode" else target.encode()
            if fmt == "base64":
                out = (base64.b64encode if op == "encode" else base64.b64decode)(data)
            elif fmt == "base32":
                out = (base64.b32encode if op == "encode" else base64.b32decode)(data)
            elif fmt == "base16-hex":
                out = binascii.hexlify(data) if op == "encode" else binascii.unhexlify(data)
            elif fmt == "url":
                from urllib.parse import quote, unquote
                out = quote(target).encode() if op == "encode" else unquote(target).encode()
            elif fmt == "rot13":
                import codecs
                out = codecs.encode(target, "rot_13").encode()
            elif fmt == "ascii85":
                out = (base64.a85encode if op == "encode" else base64.a85decode)(data)
            else:
                on_stderr(f"unknown format {fmt}\n")
                return ToolResult(exit_code=2)
        except Exception as e:
            on_stderr(f"{type(e).__name__}: {e}\n")
            return ToolResult(exit_code=1)
        try:
            text = out.decode()
        except UnicodeDecodeError:
            text = out.hex()
        on_stdout(text + "\n")
        return ToolResult(exit_code=0,
                          findings=[{"title": f"{fmt} {op}: {text[:200]}", "severity": "info",
                                     "data": {"input": target, "output": text, "format": fmt, "operation": op}}],
                          meta={"format": fmt, "operation": op})


registry.register(OpensslHashTool())
registry.register(OpensslCipherTool())
registry.register(CodecTool())
