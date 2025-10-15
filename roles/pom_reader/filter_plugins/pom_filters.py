# -*- coding: utf-8 -*-
# Minimal helpers for POM parsing/updating from Ansible
from __future__ import annotations
import re
from typing import Iterable, Tuple, Dict

_PROP_RE = re.compile(r"^\$\{([^}]+)\}$")

def xml_texts(matches: Iterable) -> list[str]:
    """
    Flatten community.general.xml 'matches' into a list of trimmed strings.
    Each match is typically a dict like {'{ns}tag': 'value'}.
    """
    out = []
    if not matches:
        return out
    for m in matches:
        if isinstance(m, dict) and m:
            v = next(iter(m.values()))
        else:
            v = m if m is not None else ""
        out.append(str(v).strip())
    return out

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
        if not v:
            return "", "none"
        name = prop_name(v)
        if name:
            return props.get(name, ""), f"property:{name}"
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
            "xml_texts": xml_texts,
            "prop_name": prop_name,
            "resolve_version": resolve_version,
        }
