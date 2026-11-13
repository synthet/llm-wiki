"""Redaction for housekeeping: mask credentials and personal data before text leaves its file.

Two independent detectors guard every hand-off:

* ``secret_labels`` uses known credential patterns (the same set as the vault housekeeping harness and
  ``scripts/ci/secret_detection.py``).
* ``entropy_hits`` flags long, random-looking tokens that no pattern knows.

``redact`` masks what the patterns find plus anything that merely looks like a secret assignment,
private key, injected harness block, home path, email or private IP. Over-redaction is cheap here, a
leak is not. ``residual`` runs both detectors on redacted text; callers hold an item when it is
non-empty, so a miss in one detector is caught by the other.
"""

from __future__ import annotations

import functools
import math
import os
import re
import socket
import subprocess
from collections import Counter
from pathlib import Path

TOKEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key id", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("Credentialed URL", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@\"']+:[^\s:/@\"']+@[^\s\"']+")),
    (
        "Suspicious assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|auth[_-]?token|access[_-]?token|client[_-]?secret|password|passwd)\b"
            r"\s*[:=]\s*[\"']([A-Za-z0-9+/_=-]{16,})[\"']"
        ),
    ),
]
ALLOW_VALUE_RE = re.compile(
    r"^\$\{[A-Z0-9_]+\}$|^\{\{[^}]*\}\}$|^TODO\([^)]*\)$|^<[A-Za-z][A-Za-z0-9 _-]*>$"
    r"|(?i:\b(example|placeholder|dummy|sample|fake|redacted|changeme|your[_-]))|^x{6,}$|^\*{4,}$|^\.{3}$"
)
SECRET_FILE_RE = re.compile(
    r"(^|[\\/])(\.env(\..+)?|id_(rsa|ed25519|ecdsa)|[^\\/]*\.(pem|pfx|p12|key)|credentials\.json|secrets?\.json"
    r"|settings\.local\.json|\.netrc|\.npmrc|\.pypirc)$",
    re.I,
)
PEM_BLOCK_RE = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)", re.S)
# Any KEY/TOKEN/SECRET/PASSWORD-like name assigned a value, quoted or not, anywhere on a line
# (env files, YAML/JSON keys, shell exports, diff lines, and assignments embedded in prose).
ASSIGN_RE = re.compile(
    r"(?i)(\b(?:export\s+)?[\"']?[\w.-]*(?:key|token|secret|passw(?:or)?d|pwd|credential|auth)[\w.-]*[\"']?"
    r"\s*[:=]\s*)([\"']?)([^\s\"',;}]{4,})"
)
INJECTED_RE = re.compile(
    r"<(?P<tag>manually_attached_skills|system[-_]reminder|environment_context|INSTRUCTIONS|"
    r"available_subagent_types|available_subagent_models|dynamic_tools|dynamic_tool_namespaces|"
    r"command-[a-z]+|local-command-[a-z]+)\b[^>]*>.*?(?:</(?P=tag)\s*>|\Z)",
    re.I | re.S,
)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PRIVATE_IP_RE = re.compile(r"\b(?:10|127|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){2,3}\b")
USERS_PATH_RE = re.compile(r"(?i)(?<![A-Za-z])([A-Z]:[\\/]+Users[\\/]+|/home/|/Users/)([^\\/\s\"'`<]+)")
GENERIC_TERMS = {"user", "admin", "root", "home", "localhost", "users", "default", "runner"}
CANDIDATE_RE = re.compile(r"[A-Za-z0-9+/_=-]{32,}")
HEX_RE = re.compile(r"^[0-9a-f]+$")


def _value(match: re.Match[str]) -> str:
    if match.lastindex and match.lastindex >= 2 and match.group(2) is not None:
        return match.group(2)
    return match.group(0)


def secret_labels(text: str) -> list[str]:
    """Labels of credential patterns present in ``text``. Values are never returned."""
    return sorted(
        {
            label
            for label, pattern in TOKEN_PATTERNS
            for match in pattern.finditer(text)
            if not ALLOW_VALUE_RE.search(_value(match).strip())
        }
    )


def _entropy(token: str) -> float:
    counts = Counter(token)
    return -sum(n / len(token) * math.log2(n / len(token)) for n in counts.values())


def entropy_hits(text: str, *, threshold: float = 4.3) -> int:
    """Count long random-looking tokens (mixed case and digits, high entropy). Git SHAs (hex) are ignored."""
    hits = 0
    for match in CANDIDATE_RE.finditer(text):
        token = match.group(0).strip("=")
        if len(token) < 32 or HEX_RE.match(token.lower()) and token == token.lower():
            continue
        classes = sum(bool(re.search(p, token)) for p in (r"[a-z]", r"[A-Z]", r"\d"))
        if classes == 3 and _entropy(token) >= threshold:
            hits += 1
    return hits


@functools.lru_cache(maxsize=1)
def identity_terms() -> tuple[str, ...]:
    """Local identifiers that must not leave the machine: user and host names, git identity, HK_REDACT_TERMS."""
    terms = {
        Path.home().name,
        os.environ.get("USERNAME", ""),
        os.environ.get("USER", ""),
        os.environ.get("COMPUTERNAME", ""),
        socket.gethostname(),
    }
    for key in ("user.name", "user.email"):
        try:
            proc = subprocess.run(["git", "config", "--global", key], capture_output=True, text=True, timeout=10)
            terms.add(proc.stdout.strip())
        except (OSError, subprocess.TimeoutExpired):
            pass
    terms.update(t.strip() for t in os.environ.get("HK_REDACT_TERMS", "").split(","))
    keep = (t for t in terms if len(t) >= 3 and t.lower() not in GENERIC_TERMS)
    return tuple(sorted(keep, key=len, reverse=True))


def _term_re(term: str) -> re.Pattern[str]:
    """Distinctive terms (5+ chars) match anywhere: slugified paths and escaped text glue them to letters
    (`cusers<name>appdata`, `\\n<name>`). Short terms need word boundaries to avoid masking ordinary words."""
    if len(term) >= 5:
        return re.compile(re.escape(term), re.I)
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.I)


def residual(text: str) -> list[str]:
    """What is still risky in already-redacted text; empty means safe to hand off."""
    found = secret_labels(text)
    if any(_term_re(term).search(text) for term in identity_terms()):
        found.append("local identity term")
    if PEM_BLOCK_RE.search(text):
        found.append("Private key block")
    n = entropy_hits(text)
    if n:
        found.append(f"{n} high-entropy token(s)")
    return found


def redact(text: str, *, home: str | None = None) -> str:
    """Mask credentials, key blocks, injected harness blocks, user paths, emails and private IPs."""
    text = INJECTED_RE.sub(lambda m: f"[REDACTED:{m.group('tag')} block]", text)
    text = PEM_BLOCK_RE.sub("[REDACTED:private key block]", text)
    for label, pattern in TOKEN_PATTERNS:
        text = pattern.sub(
            lambda m, lb=label: (
                m.group(0)
                if ALLOW_VALUE_RE.search(_value(m).strip())
                else m.group(0).replace(_value(m), f"[REDACTED:{lb}]")
            ),
            text,
        )
    text = ASSIGN_RE.sub(
        lambda m: (
            m.group(0) if m.group(3).startswith("[REDACTED") else f"{m.group(1)}{m.group(2)}[REDACTED:assignment]"
        ),
        text,
    )
    home = home if home is not None else str(Path.home())
    for variant in sorted({home, home.replace("\\", "/"), home.replace("\\", "\\\\")}, key=len, reverse=True):
        if variant:
            text = re.sub(re.escape(variant), "<USER_HOME>", text, flags=re.I)
    text = USERS_PATH_RE.sub(lambda m: f"{m.group(1)}<USER>", text)
    text = EMAIL_RE.sub("<EMAIL>", text)
    for term in identity_terms():
        text = _term_re(term).sub("<USER>", text)
    text = PRIVATE_IP_RE.sub("<PRIVATE_IP>", text)

    def mask_random(m: re.Match[str]) -> str:
        return "[REDACTED:high-entropy]" if entropy_hits(m.group(0)) else m.group(0)

    return CANDIDATE_RE.sub(mask_random, text)
