"""Detection (not redaction) for sanitize: precise enough to run over tracked source without flagging every `key:`.

`redact()` over-masks on purpose, so it is the wrong tool for deciding whether a tracked file holds a secret.
These checks report finding types and line numbers only; values are never returned.

Known trade-offs: values shorter than 6 characters, and lower-case word values under keys that are not explicitly
password/secret keys, are not flagged; snake/kebab-case identifiers such as `opal_river_77` are treated as names.
"""

from __future__ import annotations

import bisect
import math
import os
import re
import socket
from collections import Counter
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
# `Password=...` / `Pwd=...` inside a connection string, wherever it sits on the line (JSON values, URLs, prose).
# Only where a connection-string field starts (line start or after ; " ' space ? & { , ( ), so `DB_PASSWORD=` is
# left to the assignment rule instead of being counted twice.
CONN_PASSWORD_RE = re.compile(r"(?im)(?:^|(?<=[;\"'\s?&{,(]))(?:password|pwd)[ \t]*=[ \t]*([^;\"'\s,}]{4,200})")
SECRET_WORDS = (
    "password", "passwd", "pwd", "secret", "token", "apikey", "accesskey", "privatekey", "secretkey", "signingkey",
    "encryptionkey", "masterkey", "clientkey", "credential", "credentials",
)  # fmt: skip
# Keys named for a password hold one whatever the value looks like (`DB_PASSWORD=sunshinesky`). Other secret words
# (`secret`, `token`, `credentials`) also name tools, flags and enum values, so they need a credential-shaped value.
STRONG_WORDS = ("password", "passwd", "pwd")
PLACEHOLDER_RE = re.compile(
    r"^(?:\$[A-Za-z_]\w*|\$\{[A-Za-z_]\w*(?::?[-=?+][^{}]*)?\}|%[A-Za-z_]\w*%|<[^<>]{1,80}>|\{\{[^{}]*\}\})$"
)
# A key whose last part names something other than the secret itself (INAT_OAUTH_TOKEN_URL, token_path, --token-bg).
NOT_SECRET_SUFFIXES = {
    "url", "uri", "path", "file", "dir", "name", "id", "env", "header", "type", "endpoint", "kind", "label",
    "length", "size", "count", "ttl", "expiry", "expires", "format", "prefix", "policy", "hint", "field",
    "prompt", "rule", "rules", "min", "max", "reset", "change", "required", "bg", "fg", "color", "colour", "style",
    "class", "icon", "width", "height", "input", "placeholder", "regex", "pattern", "mode", "enabled", "flag",
}  # fmt: skip
# `key` is a secret only when nothing says it is a different kind of key (database, cache, i18n, UI, ...).
NOT_SECRET_KEY_QUALIFIERS = {
    "primary", "foreign", "sort", "storage", "loc", "toggle", "public", "idempotency", "cache", "partition", "row",
    "unique", "composite", "map", "dict", "list", "item", "lookup", "hot", "short", "shortcut", "keyboard", "i18n",
    "translation", "message", "msg", "react", "query", "group", "shard", "hash", "index", "natural", "surrogate",
    "object", "entry", "route", "state", "store", "range", "description", "path", "tool", "unit", "review",
    "provider", "embedded", "detector", "config", "setting", "settings", "metric", "event", "column", "table",
    "external", "category",
}  # fmt: skip
PASSWORD_SYMBOLS = set("!@#$%^&*=?~")
IDENTIFIER_RE = re.compile(r"[a-z][a-z0-9]*(?:[_+-][a-z0-9]+)+")  # word_word_9_word, wiki-graph-cache-v2, ctrl+k
DOTTED_RE = re.compile(r"[A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)+")  # module.attr, a.b.c keys, reverse-domain names
VERSION_RE = re.compile(r"[\^~<>=v]?\d+(?:\.[\dx*]+)*(?:[-+][\w.]+)?")


def _parts(key: str) -> list[str]:
    return [p.lower() for p in re.split(r"[_.-]+|(?<=[a-z0-9])(?=[A-Z])", key) if p]


def key_strength(key: str, *, code: bool) -> str | None:
    """None when the key does not name a secret, "strong" for password/secret keys, "weak" for token/key names.

    DB_PASSWORD, client-secret: strong. apiKey, API_TOKEN_PROD, APP_KEY, STRIPE_KEY: weak. tokenizer, monkey, *_URL,
    primaryKey, locKey, STORAGE_KEY, --token-bg: None. A bare `key` counts only outside source code (`KEY=` in .env),
    since `key=` in code is a JSX/React or dict key.
    """
    if key.startswith("--"):
        return None  # CSS custom property
    parts = _parts(key)
    if not parts or parts[-1] in NOT_SECRET_SUFFIXES or "public" in parts:
        return None  # public keys and .NET publicKeyToken are meant to be shared
    joined = parts + [a + b for a, b in zip(parts, parts[1:], strict=False)]
    if any(p.endswith(w) for p in joined for w in STRONG_WORDS):
        return "strong"
    if any(p.endswith(w) for p in joined for w in SECRET_WORDS):
        return "weak"
    if "key" in parts:
        if set(parts) & NOT_SECRET_KEY_QUALIFIERS:
            return None
        if parts == ["key"] and code:
            return None
        return "weak"
    return None


def secret_key(key: str) -> bool:
    return key_strength(key, code=False) is not None


def _entropy(v: str) -> float:
    counts = Counter(v)
    return -sum(n / len(v) * math.log2(n / len(v)) for n in counts.values())


def credential_like(value: str, *, strong: bool = False) -> bool:
    """A value that looks like a credential rather than an identifier, expression, URL, path or version.

    `map_object_names`, `${VAR:?x}`, `$(cat f)`, `#0a0a0a`, `https://...`, `src/app`, `^1.2.3` are not credentials;
    `hunter2xyz`, `p@ss;word!` and a random AWS-style key with `/` are. Under a strong (password/secret) key any literal
    of 6+ characters that is not one of those counts, so `letmein` and `sunshinesky` are flagged.
    """
    v = value.strip()
    if len(v) < (6 if strong else 8):
        return False
    if v.startswith("$") or "$(" in v or "${" in v or "%%" in v or "`" in v:
        return False  # shell or template expression
    if re.fullmatch(r"#[0-9a-fA-F]{3,8};?", v):
        return False  # colour
    if "://" in v or "\\" in v or v.startswith(("/", "./", "../", "~")) or re.match(r"[A-Za-z]:[\\/]", v):
        return False  # URL or path
    if "/" in v:  # only a long, random value with slashes is a key (AWS secret keys, base64); `src/app/main` is a path
        classes = sum(bool(re.search(p, v)) for p in (r"[a-z]", r"[A-Z]", r"\d"))
        return len(v) >= 20 and classes == 3 and _entropy(v) >= 3.5
    if DOTTED_RE.fullmatch(v) or VERSION_RE.fullmatch(v) or IDENTIFIER_RE.fullmatch(v):
        return False
    if " " in v:
        return False
    if strong:
        return True
    if v.isalpha() or re.fullmatch(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+", v):
        return False  # words, PascalCase and UPPER_SNAKE enum values (ResumeTokenInvalid, INVALID_TOKEN_2)
    has_digit, has_alpha = any(c.isdigit() for c in v), any(c.isalpha() for c in v)
    mixed_case = any(c.islower() for c in v) and any(c.isupper() for c in v)
    return (has_digit and has_alpha) or (mixed_case and len(v) >= 12) or (has_alpha and bool(PASSWORD_SYMBOLS & set(v)))


EXAMPLE_PASSWORDS = {"pass", "password", "passwd", "pwd", "secret", "token", "xxx", "xxxx", "changeme", "p", "pw"}


def _example_url(url: str) -> bool:
    """A credentialed-URL example in docs or pattern tables: its password part is a stock placeholder ("pass")."""
    m = re.match(r"[^:]+://[^:@/]+:([^@/]+)@", url)
    return bool(m) and (m.group(1).lower() in EXAMPLE_PASSWORDS or _placeholder(m.group(1)))


def _placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_RE.match(value.strip())) or bool(ALLOW_VALUE_RE.search(value))


class _Lines:
    """Line numbers by bisecting precomputed newline offsets (linear overall, not a count per match)."""

    def __init__(self, text: str):
        self.newlines = [m.start() for m in re.finditer("\n", text)]

    def __call__(self, pos: int) -> int:
        return bisect.bisect_left(self.newlines, pos) + 1


def secret_findings(text: str, path: str) -> dict[str, list[int]]:
    """{finding type: [line numbers]} for credentials and secret assignments in text."""
    text = text.replace("\ufeff", "")
    line = _Lines(text)
    found: dict[str, list[int]] = {}

    def add(label: str, pos: int) -> None:
        found.setdefault(label, []).append(line(pos))

    for label, pattern in TOKEN_PATTERNS:
        for m in pattern.finditer(text):
            if ALLOW_VALUE_RE.search(_value(m).strip()):
                continue
            if label == "Credentialed URL" and _example_url(m.group(0)):
                continue
            add(label, m.start())
    for m in PEM_BLOCK_RE.finditer(text):
        add("Private key block", m.start())
    code = bool(CODE_FILE_RE.search(path))
    for pat in (QUOTED_ASSIGN_RE,) if code else (UNQUOTED_ASSIGN_RE, QUOTED_ASSIGN_RE):
        for m in pat.finditer(text):
            strength = key_strength(m.group(1), code=code)
            if strength and not _placeholder(m.group(2)) and credential_like(m.group(2), strong=strength == "strong"):
                add("secret assignment", m.start())
    for m in CONN_PASSWORD_RE.finditer(text):
        value = m.group(1)
        # In code, `connect(password=password)` is a keyword argument; a connection string there sits inside a quoted
        # literal, right after `;` or a quote.
        if code and (m.start() == 0 or text[m.start() - 1] not in ";\"'"):
            continue
        if "(" in value or "[" in value or _placeholder(value) or value.lower() in EXAMPLE_PASSWORDS:
            continue
        if credential_like(value, strong=True):
            add("connection-string password", m.start())
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
    """{type: [lines]} for this machine's home path, user and host names, and private IPs.

    Git identity and emails are deliberately not checked here: they are expected in LICENSE and author fields. Other
    people's profile paths (`C:\\Users\\alice` in docs) are examples, not this machine's data.
    """
    line = _Lines(text)
    found: dict[str, list[int]] = {}
    lower = text.lower()
    for term in local_terms():
        start = 0
        t = term.lower()
        while (i := lower.find(t, start)) >= 0:
            label = "home path" if ("\\" in term or "/" in term) else "user or host name"
            found.setdefault(label, []).append(line(i))
            start = i + len(t)
    for m in PRIVATE_IP_RE.finditer(text):
        if not m.group(0).startswith("127."):
            found.setdefault("private IP", []).append(line(m.start()))
    return {k: sorted(set(v)) for k, v in found.items()}
