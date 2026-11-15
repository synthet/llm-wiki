"""Detection (not redaction) for sanitize: precise enough to run over tracked source without flagging every `key:`.

`redact()` over-masks on purpose, so it is the wrong tool for deciding whether a tracked file holds a secret.
These checks report finding types and line numbers only; values are never returned.
"""

from __future__ import annotations

import os
import re
import socket
from pathlib import Path

from .redact import ALLOW_VALUE_RE, PEM_BLOCK_RE, PRIVATE_IP_RE, TOKEN_PATTERNS, _value

# Source code: `token = get_token()` is a variable, so only a quoted literal counts there. Every other text file
# (.env, .ini, .yaml, Dockerfile, shell, notes, extensionless) also counts an unquoted value.
CODE_FILE_RE = re.compile(
    r"\.(py|pyi|js|mjs|cjs|jsx|ts|tsx|go|rs|java|kt|kts|scala|c|h|cc|cpp|hpp|cs|fs|rb|php|swift|m|mm|lua|dart|ex|exs"
    r"|clj|vue|svelte)$",
    re.I,
)
UNQUOTED_ASSIGN_RE = re.compile(
    r"(?im)^[+]?[ \t]*(?:-[ \t]+)?(?:(?:export|set|env)[ \t]+|\$env:)?"
    r"[\"']?([A-Za-z0-9_.-]{1,80})[\"']?[ \t]*[:=][ \t]*"
    r"[\"']?(<[^<>\n]{1,80}>|[^\s\"']{6,200})"
)
QUOTED_ASSIGN_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_.-])[\"']?([A-Za-z0-9_.-]{1,80})[\"']?[ \t]*(?::[ \t]*[A-Za-z0-9_\[\], .|]{1,40}?[ \t]*)?[:=]"
    r"[ \t]*[\"']([^\"'\n]{6,200})[\"']"
)
SECRET_WORDS = (
    "password", "passwd", "pwd", "secret", "token", "apikey", "accesskey", "privatekey", "secretkey", "signingkey",
    "encryptionkey", "masterkey", "clientkey", "credential", "credentials",
)  # fmt: skip
PLACEHOLDER_RE = re.compile(
    r"^(?:\$[A-Za-z_]\w*|\$\{[A-Za-z_]\w*(?::?[-=?+][^{}]*)?\}|%[A-Za-z_]\w*%|<[^<>]{1,80}>|\{\{[^{}]*\}\})$"
)
# A key whose last part names something other than the secret itself (INAT_OAUTH_TOKEN_URL, token_path).
NOT_SECRET_SUFFIXES = {
    "url", "uri", "path", "file", "dir", "name", "id", "env", "header", "type", "endpoint", "kind", "label",
    "length", "size", "count", "ttl", "expiry", "expires", "format", "prefix",
}  # fmt: skip
PASSWORD_SYMBOLS = set("!@#$%^&*+=?~")


def secret_key(key: str) -> bool:
    """DB_PASSWORD, apiKey, client-secret, API_TOKEN_PROD, APP_KEY, KEY: yes. tokenizer, monkey, author, *_URL: no."""
    parts = [p.lower() for p in re.split(r"[_.-]+|(?<=[a-z0-9])(?=[A-Z])", key) if p]
    if parts and parts[-1] in NOT_SECRET_SUFFIXES:
        return False
    joined = parts + [a + b for a, b in zip(parts, parts[1:], strict=False)]
    return "key" in parts or any(p.endswith(w) for p in joined for w in SECRET_WORDS)


def credential_like(value: str) -> bool:
    """A value that looks like a credential rather than an identifier, word, URL, path or version range.

    Detection only (tracked files are not redacted): `map_object_names`, `secret`, `https://...`, `^1.2.3` are not
    credentials; `hunter2xyz`, `opalriver77`, `Zq9Zq9...`, `p@ss;word!` are.
    """
    v = value.strip()
    if len(v) < 8 or " " in v or "://" in v or "/" in v or "\\" in v:
        return False
    if re.fullmatch(r"[A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)+", v):
        return (
            False  # dotted identifier: module.attr, a.b.c config keys, reverse-domain names (JWTs have their own rule)
        )
    if re.fullmatch(r"[\^~<>=v]?\d+(?:\.[\dx*]+)*(?:[-+][\w.]+)?", v):
        return False  # version or range
    has_digit, has_alpha = any(c.isdigit() for c in v), any(c.isalpha() for c in v)
    mixed_case = any(c.islower() for c in v) and any(c.isupper() for c in v)
    return (has_digit and has_alpha) or (mixed_case and len(v) >= 12) or (has_alpha and bool(PASSWORD_SYMBOLS & set(v)))


EXAMPLE_PASSWORDS = {"pass", "password", "passwd", "pwd", "secret", "token", "xxx", "xxxx", "changeme", "p", "pw"}


def _example_url(url: str) -> bool:
    """`scheme://user:pass@host` in docs and pattern tables: the password part is a stock placeholder."""
    m = re.match(r"[^:]+://[^:@/]+:([^@/]+)@", url)
    return bool(m) and (m.group(1).lower() in EXAMPLE_PASSWORDS or _placeholder(m.group(1)))


def _placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_RE.match(value.strip())) or bool(ALLOW_VALUE_RE.search(value))


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def secret_findings(text: str, path: str) -> dict[str, list[int]]:
    """{finding type: [line numbers]} for credentials and secret assignments in text."""
    text = text.replace("﻿", "")
    found: dict[str, list[int]] = {}

    def add(label: str, pos: int) -> None:
        found.setdefault(label, []).append(_line(text, pos))

    for label, pattern in TOKEN_PATTERNS:
        for m in pattern.finditer(text):
            if ALLOW_VALUE_RE.search(_value(m).strip()):
                continue
            if label == "Credentialed URL" and _example_url(m.group(0)):
                continue
            add(label, m.start())
    for m in PEM_BLOCK_RE.finditer(text):
        add("Private key block", m.start())
    pats = (QUOTED_ASSIGN_RE,) if CODE_FILE_RE.search(path) else (UNQUOTED_ASSIGN_RE, QUOTED_ASSIGN_RE)
    for pat in pats:
        for m in pat.finditer(text):
            if secret_key(m.group(1)) and not _placeholder(m.group(2)) and credential_like(m.group(2)):
                add("secret assignment", m.start())
    return {k: sorted(set(v)) for k, v in found.items()}


def local_terms() -> list[str]:
    """Machine-identifying strings: the home path in its spellings, the user name and the host name."""
    home = str(Path.home())
    terms = {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}
    for t in (
        Path.home().name,
        os.environ.get("USERNAME", ""),
        os.environ.get("COMPUTERNAME", ""),
        socket.gethostname(),
    ):
        if len(t) >= 5:
            terms.add(t)
    return sorted((t for t in terms if t), key=len, reverse=True)


def local_findings(text: str) -> dict[str, list[int]]:
    """{type: [lines]} for home paths, other users' profile paths, the host name and private IPs.

    Git identity and emails are deliberately not checked here: they are expected in LICENSE and author fields.
    """
    found: dict[str, list[int]] = {}
    lower = text.lower()
    for term in local_terms():
        start = 0
        t = term.lower()
        while (i := lower.find(t, start)) >= 0:
            label = "home path" if ("\\" in term or "/" in term) else "user or host name"
            found.setdefault(label, []).append(_line(text, i))
            start = i + len(t)
    # Other people's profile paths (`C:\Users\alice` in docs) are examples, not this machine's data; only the local
    # home path, user and host names above count.
    for m in PRIVATE_IP_RE.finditer(text):
        if not m.group(0).startswith("127."):
            found.setdefault("private IP", []).append(_line(text, m.start()))
    return {k: sorted(set(v)) for k, v in found.items()}
