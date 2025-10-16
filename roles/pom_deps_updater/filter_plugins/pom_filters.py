# -*- coding: utf-8 -*-
# Minimal helpers for POM parsing/updating from Ansible
from __future__ import annotations
import re
from typing import Iterable, Tuple, Dict, Any, List

_PROP_RE = re.compile(r"^\$\{([^}]+)\}$")

def _first_dict_value(d: Dict[Any, Any]) -> Any:
    # community.general.xml returns items like {'{ns}tag': 'value'}
    # we just take the first value
    return next(iter(d.values())) if d else ""

def xml_texts(matches: Iterable[Any]) -> List[str]:
    """
    Flatten community.general.xml 'matches' into a list of trimmed strings.
    Each element is typically a dict like {'{ns}tag': 'value'}.
    Tolerates strings and non-list inputs gracefully.
    """
    if matches is None:
        return []
    # If someone passed a bare string, treat it as a single item
    if isinstance(matches, (str, bytes)):
        matches = [matches]  # type: ignore[assignment]
    out: List[str] = []
    for m in matches:
        if isinstance(m, dict):
            v = _first_dict_value(m)
        else:
            v = m if m is not None else ""
        out.append(str(v).strip())
    return out

def xml_first(matches: Iterable[Any], default: str = "") -> str:
    """Return first trimmed text from xml 'matches', or default if empty."""
    t = xml_texts(matches)
    return t[0] if t else default

def xml_first_trim(matches: Iterable[Any], default: str = "") -> str:
    """Alias to xml_first for readability; ensures a stripped string."""
    return xml_first(matches, default).strip()

# ---------- Result-object helpers (for loop-registered tasks) ----------

def xml_matches(result: Any) -> list:
    """Safely get .matches from a loop-registered xml task result."""
    if not isinstance(result, dict):
        return []
    m = result.get("matches", [])
    return m if isinstance(m, list) else []

def xml_texts_from_result(result: Any) -> List[str]:
    """xml_texts on a single loop result dict."""
    return xml_texts(xml_matches(result))

def xml_first_from_result(result: Any, default: str = "") -> str:
    """First trimmed text from a loop result dict, or default."""
    return xml_first(xml_matches(result), default)

def xml_len(result: Any) -> int:
    """Length of matches on a loop result dict."""
    return len(xml_matches(result))

# ---------- Property/management helpers ----------

def prop_name(value: str) -> str:
    """Return property name inside ${...} or '' if not a property ref."""
    if not value:
        return ""
    m = _PROP_RE.match(value.strip())
    return m.group(1) if m else ""

def resolve_version(explicit: str, managed: str = "", props: Dict[str, str] | None = None) -> Tuple[str, str]:
    """
    Decide an effective version for a plugin/dependency:
    1) Use explicit; if it's a ${prop} and props has it, resolve to props[prop].
    2) Else use managed; if it's a ${prop} and props has it, resolve similarly.
    Returns (effective_value, source) where source ∈ {'explicit','property:<name>','pluginManagement','none'}.
    """
    props = props or {}

    def _resolve(v: str, fallback_source: str) -> Tuple[str, str]:
        v = (v or "").strip()
        if not v:
            return "", "none"
        name = prop_name(v)
        if name:
            return (props.get(name, "") or "").strip(), f"property:{name}"
        return v, fallback_source

    val, src = _resolve(explicit, "explicit")
    if val:
        return val, src

    val, src = _resolve(managed, "pluginManagement")
    if val:
        return val, src

    return "", "none"

class FilterModule(object):
    def filters(self):
        return {
            # list-based
            "xml_texts": xml_texts,
            "xml_first": xml_first,
            "xml_first_trim": xml_first_trim,
            # result-based
            "xml_matches": xml_matches,
            "xml_texts_from_result": xml_texts_from_result,
            "xml_first_from_result": xml_first_from_result,
            "xml_len": xml_len,
            # props/version
            "prop_name": prop_name,
            "resolve_version": resolve_version,
        }