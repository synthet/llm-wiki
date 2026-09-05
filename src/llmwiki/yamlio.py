"""YAML frontmatter I/O.

Uses PyYAML when it is importable; otherwise falls back to a small, dependency
-free parser/dumper that understands the subset of YAML this project emits
(scalars, nested mappings by indentation, block lists of scalars and of
mappings). The fallback exists so `llmwiki` works in a bare Python environment;
when PyYAML is present it is always preferred.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Tuple

try:  # pragma: no cover - exercised indirectly
    import yaml as _yaml
except Exception:  # pragma: no cover
    _yaml = None

_FRONTMATTER_RE = re.compile(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)


def has_pyyaml() -> bool:
    return _yaml is not None


def split_frontmatter(text: str) -> Tuple[dict, str, str]:
    """Split ``text`` into (frontmatter_dict, body, raw_frontmatter_text).

    Returns an empty dict and the full text as body when no frontmatter block
    is present. Raises ``ValueError`` when the frontmatter is malformed.
    """
    if not text.startswith("---"):
        return {}, text, ""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("frontmatter opened with '---' but was not closed")
    raw = m.group(1)
    body = text[m.end():]
    data = load_yaml(raw)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data, body, raw


def load_yaml(text: str) -> Any:
    if _yaml is not None:
        return _yaml.safe_load(text)
    return _fallback_load(text)


def dump_yaml(obj: Any) -> str:
    if _yaml is not None:
        return _yaml.safe_dump(
            obj, sort_keys=False, allow_unicode=True, default_flow_style=False
        )
    return _fallback_dump(obj)


def render_page(frontmatter: dict, body: str) -> str:
    """Serialise a page from frontmatter + body into a full Markdown string."""
    fm = dump_yaml(frontmatter).rstrip("\n")
    body = body.lstrip("\n")
    return f"---\n{fm}\n---\n\n{body}"


# ---------------------------------------------------------------------------
# Fallback dumper
# ---------------------------------------------------------------------------
def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    s = str(value)
    if s == "":
        return '""'
    special = ":#{}[]!*&|>%@`\"'"
    needs_quote = (
        s != s.strip()
        or s[0] in "-?:,[]{}#&*!|>'\"%@` "
        or any(c in s for c in special and ":#")
        or s.lower() in {"null", "true", "false", "yes", "no", "~"}
    )
    if ": " in s or s.endswith(":") or " #" in s:
        needs_quote = True
    if needs_quote:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _fallback_dump(obj: Any, indent: int = 0) -> str:
    pad = "  " * indent
    lines = []
    if isinstance(obj, dict):
        if not obj:
            return pad + "{}\n"
        for k, v in obj.items():
            if isinstance(v, dict) and v:
                lines.append(f"{pad}{k}:")
                lines.append(_fallback_dump(v, indent + 1))
            elif isinstance(v, (list, tuple)) and v:
                lines.append(f"{pad}{k}:")
                lines.append(_fallback_dump(list(v), indent))
            elif isinstance(v, (list, tuple)):
                lines.append(f"{pad}{k}: []")
            elif isinstance(v, dict):
                lines.append(f"{pad}{k}: {{}}")
            else:
                lines.append(f"{pad}{k}: {_scalar(v)}")
        return "\n".join(x for x in lines if x != "") + "\n"
    if isinstance(obj, (list, tuple)):
        for item in obj:
            if isinstance(item, dict) and item:
                inner = _fallback_dump(item, indent + 1)
                inner = inner[len(pad) + 2:]  # strip leading pad of first line
                lines.append(f"{pad}- {inner.rstrip()}")
            elif isinstance(item, (list, tuple)):
                lines.append(f"{pad}-")
                lines.append(_fallback_dump(list(item), indent + 1))
            else:
                lines.append(f"{pad}- {_scalar(item)}")
        return "\n".join(lines) + "\n"
    return pad + _scalar(obj) + "\n"


# ---------------------------------------------------------------------------
# Fallback loader (indentation-based subset)
# ---------------------------------------------------------------------------
def _parse_scalar(tok: str) -> Any:
    tok = tok.strip()
    if tok == "" or tok == "~" or tok.lower() == "null":
        return None
    if tok.lower() == "true":
        return True
    if tok.lower() == "false":
        return False
    if (tok[0] == '"' and tok[-1] == '"') or (tok[0] == "'" and tok[-1] == "'"):
        return tok[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if tok in ("[]", "{}"):
        return [] if tok == "[]" else {}
    if tok.startswith("[") and tok.endswith("]"):
        inner = tok[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(p) for p in _split_flow(inner)]
    if tok.startswith("{") and tok.endswith("}"):
        inner = tok[1:-1].strip()
        if not inner:
            return {}
        out = {}
        for part in _split_flow(inner):
            k, sep, v = part.partition(":")
            if sep:
                out[str(_parse_scalar(k.strip()))] = _parse_scalar(v.strip())
        return out
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        pass
    return tok


def _split_flow(s: str) -> list:
    out, depth, buf, q = [], 0, "", None
    for ch in s:
        if q:
            buf += ch
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
            buf += ch
        elif ch in "[{":
            depth += 1
            buf += ch
        elif ch in "]}":
            depth -= 1
            buf += ch
        elif ch == "," and depth == 0:
            out.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        out.append(buf)
    return out


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _unquote_key(k: str) -> str:
    k = k.strip()
    if len(k) >= 2 and k[0] == k[-1] and k[0] in "\"'":
        return k[1:-1]
    return k


def _split_map_key(content: str):
    """Split ``key: value`` respecting quotes/brackets. Returns (key, sep, rest).

    ``sep`` is ':' when a real mapping colon (followed by whitespace or EOL and
    not inside quotes/brackets) was found, else ''. Avoids splitting on the
    ':' inside values like ``uri: https://...``.
    """
    depth, q = 0, None
    for i, ch in enumerate(content):
        if q:
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ":" and depth == 0:
            if i + 1 >= len(content) or content[i + 1] in " \t":
                return content[:i], ":", content[i + 1:]
    return content, "", ""


def _fallback_load(text: str) -> Any:
    raw = [ln.rstrip() for ln in text.splitlines()]
    n = len(raw)
    pos = [0]

    def is_blank_or_comment(i: int) -> bool:
        s = raw[i].strip()
        return s == "" or s.startswith("#")

    def next_meaningful() -> int:
        i = pos[0]
        while i < n and is_blank_or_comment(i):
            i += 1
        return i

    def parse_block_scalar(indicator: str, parent_indent: int) -> str:
        style = indicator[0]
        chomp = "clip"
        for ch in indicator[1:]:
            if ch == "-":
                chomp = "strip"
            elif ch == "+":
                chomp = "keep"
        collected = []
        while pos[0] < n:
            line = raw[pos[0]]
            if line.strip() == "":
                collected.append("")
                pos[0] += 1
                continue
            if _indent(line) <= parent_indent:
                break
            collected.append(line)
            pos[0] += 1
        while collected and collected[-1] == "":
            if chomp == "keep":
                break
            collected.pop()
        content_lines = [ln for ln in collected if ln.strip()]
        base = min((_indent(ln) for ln in content_lines), default=parent_indent + 1)
        stripped = [ln[base:] if len(ln) >= base else "" for ln in collected]
        if style == "|":
            text_out = "\n".join(stripped)
        else:  # folded '>'
            paras, cur = [], []
            for ln in stripped:
                if ln == "":
                    paras.append(" ".join(cur))
                    cur = []
                else:
                    cur.append(ln)
            if cur:
                paras.append(" ".join(cur))
            text_out = "\n".join(paras)
        if chomp == "strip":
            text_out = text_out.rstrip("\n")
        elif chomp == "clip":
            text_out = text_out.rstrip("\n")
        return text_out

    def parse_node(min_indent: int) -> Any:
        i = next_meaningful()
        if i >= n:
            return None
        ind = _indent(raw[i])
        if ind < min_indent:
            return None
        s = raw[i].strip()
        if s == "-" or s.startswith("- "):
            return parse_seq(ind)
        return parse_map(ind)

    def parse_map(cur: int) -> dict:
        out: dict = {}
        while True:
            i = next_meaningful()
            if i >= n:
                break
            ind = _indent(raw[i])
            if ind != cur:
                break
            s = raw[i].strip()
            if s.startswith("- "):
                break
            key, sep, rest = _split_map_key(s)
            if sep == "":
                break
            key = _unquote_key(key)
            rest = rest.strip()
            pos[0] = i + 1
            if rest and rest[0] in "|>":
                out[key] = parse_block_scalar(rest, cur)
            elif rest == "":
                j = next_meaningful()
                if j < n and _indent(raw[j]) > cur:
                    out[key] = parse_node(cur + 1)
                elif j < n and _indent(raw[j]) == cur and raw[j].strip().startswith("- "):
                    out[key] = parse_seq(cur)
                else:
                    out[key] = None
            else:
                out[key] = _parse_scalar(rest)
        return out

    def parse_seq(cur: int) -> list:
        out: list = []
        while True:
            i = next_meaningful()
            if i >= n:
                break
            ind = _indent(raw[i])
            if ind != cur:
                break
            s = raw[i].strip()
            if not (s == "-" or s.startswith("- ")):
                break
            pos[0] = i + 1
            if s == "-":
                out.append(parse_node(cur + 1))
                continue
            content = s[2:]
            dash_col = ind + 2
            key, sep, rest = _split_map_key(content)
            if sep == ":":
                submap: dict = {}
                key = _unquote_key(key)
                rest = rest.strip()
                if rest and rest[0] in "|>":
                    submap[key] = parse_block_scalar(rest, dash_col - 1)
                elif rest == "":
                    j = next_meaningful()
                    if j < n and _indent(raw[j]) >= dash_col:
                        submap[key] = parse_node(dash_col)
                    else:
                        submap[key] = None
                else:
                    submap[key] = _parse_scalar(rest)
                submap.update(parse_map(dash_col))
                out.append(submap)
            else:
                out.append(_parse_scalar(content))
        return out

    result = parse_node(0)
    return result if result is not None else {}
