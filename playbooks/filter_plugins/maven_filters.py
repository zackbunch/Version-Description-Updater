# -*- coding: utf-8 -*-
# Minimal helpers for POM plugin/version extraction from Ansible
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from typing import Tuple, Dict, List

# ----------------------------------------------------------------------
# Property/version resolution
# ----------------------------------------------------------------------
_PROP_RE = re.compile(r"^\$\{([^}]+)\}$")

def prop_name(value: str) -> str:
    """Return property name inside ${...} or '' if not a property ref."""
    if not value:
        return ""
    m = _PROP_RE.match(value.strip())
    return m.group(1) if m else ""

def resolve_version(
    explicit: str, managed: str = "", props: Dict[str, str] | None = None
) -> Tuple[str, str]:
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

# ----------------------------------------------------------------------
# Namespace-agnostic XML traversal helpers
# ----------------------------------------------------------------------
def _nsless(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag

def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""

def _child_by_local(el: ET.Element, name: str) -> ET.Element | None:
    for c in list(el):
        if _nsless(c.tag) == name:
            return c
    return None

def _children_by_local(el: ET.Element, name: str) -> List[ET.Element]:
    return [c for c in list(el) if _nsless(c.tag) == name]

def _iter_plugins(root: ET.Element):
    """Yield <plugin> elements under <project>/<build>/<plugins> (namespace-agnostic)."""
    for child in list(root):
        if _nsless(child.tag) != "build":
            continue
        for b in list(child):
            if _nsless(b.tag) != "plugins":
                continue
            for plugin in list(b):
                if _nsless(plugin.tag) == "plugin":
                    yield plugin

# ----------------------------------------------------------------------
# Public filters
# ----------------------------------------------------------------------
def maven_plugins(pom_xml: str, props: Dict[str, str] | None = None) -> List[Dict[str, str]]:
    """
    Returns:
      [{'artifactId': 'maven-compiler-plugin', 'version': '3.5.1', 'source': 'explicit'}, ...]
    Explicit-only unless the version is a ${prop} and `props` resolves it.
    """
    props = props or {}
    root = ET.fromstring(pom_xml)
    out: List[Dict[str, str]] = []
    for p in _iter_plugins(root):
        aid = _text(_child_by_local(p, "artifactId"))
        explicit = _text(_child_by_local(p, "version"))
        eff, src = resolve_version(explicit, managed="", props=props)
        out.append({"artifactId": aid, "version": eff, "source": src if eff else "none"})
    return out

def maven_plugin_deps(pom_xml: str, props: Dict[str, str] | None = None) -> List[Dict[str, str]]:
    """
    Returns:
      [{'plugin':'maven-surefire-plugin','artifactId':'surefire-junit47','version':'2.19.1','source':'explicit'}, ...]
    """
    props = props or {}
    root = ET.fromstring(pom_xml)
    out: List[Dict[str, str]] = []
    for p in _iter_plugins(root):
        plugin_aid = _text(_child_by_local(p, "artifactId"))
        deps_parent = _child_by_local(p, "dependencies")
        if deps_parent is None:
            continue
        for d in _children_by_local(deps_parent, "dependency"):
            dep_aid = _text(_child_by_local(d, "artifactId"))
            dep_ver = _text(_child_by_local(d, "version"))
            eff, src = resolve_version(dep_ver, managed="", props=props)
            out.append({
                "plugin": plugin_aid,
                "artifactId": dep_aid,
                "version": eff,
                "source": src if eff else "none",
            })
    return out

class FilterModule(object):
    def filters(self):
        return {
            "maven_plugins": maven_plugins,
            "maven_plugin_deps": maven_plugin_deps,
            "resolve_version": resolve_version,
            "prop_name": prop_name,
        }