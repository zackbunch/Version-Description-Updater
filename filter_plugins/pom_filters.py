# filter_plugins/pom_filters.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Tuple

# --------------------------------------------------------------------
# Regex for ${property.name}
# --------------------------------------------------------------------
_PROP_RE = re.compile(r"^\s*\$\{([^}]+)\}\s*$")


# ====================================================================
# XML helpers (for community.general.xml results)
# ====================================================================
def xml_texts(matches: Any) -> List[str]:
    """
    Flatten community.general.xml 'matches' output to a list of trimmed strings.
    Accepts dicts, strings/bytes, lists, or None.
    """
    if matches is None:
        return []
    if isinstance(matches, (str, bytes)):
        matches = [matches]  # type: ignore[assignment]
    out: List[str] = []
    for m in matches:
        if isinstance(m, dict) and m:
            v = next(iter(m.values()))
        else:
            v = m if m is not None else ""
        if isinstance(v, bytes):
            v = v.decode()
        out.append(str(v).strip())
    return out


def xml_first_text(matches: Any, default: str = "") -> str:
    vals = xml_texts(matches)
    return (vals[0] if vals else default).strip()


def xml_has_any(matches: Any) -> bool:
    return len(xml_texts(matches)) > 0


# ====================================================================
# Project helpers (project_updater role)
# ====================================================================
def maven_project_meta(
    gid_matches: Any,
    aid_matches: Any,
    ver_any_matches: Any,
    ver_direct_matches: Any,
) -> Dict[str, Any]:
    """
    Normalized dict of {groupId, artifactId, version, has_direct_version}.
    """
    return {
        "groupId": xml_first_text(gid_matches),
        "artifactId": xml_first_text(aid_matches),
        "version": xml_first_text(ver_any_matches),
        "has_direct_version": xml_has_any(ver_direct_matches),
    }


def maven_desired_version(app_map: Dict[str, Any], group_id: str, artifact_id: str) -> str:
    """
    Lookup desired version from applications.json:
    Prefer 'groupId:artifactId' (lowercased), fallback to 'artifactId'.
    """
    app_map = app_map or {}
    gid = (group_id or "").strip().lower()
    aid = (artifact_id or "").strip().lower()

    if gid and aid:
        key = f"{gid}:{aid}"
        v = app_map.get(key, "")
        if isinstance(v, (str, int, float)) and str(v).strip():
            return str(v).strip()

    v = app_map.get(aid, "")
    return str(v).strip() if isinstance(v, (str, int, float)) else ""


def maven_is_property_ref(s: str) -> bool:
    return bool(_PROP_RE.match(s or ""))


def maven_prop_name(s: str) -> str:
    m = _PROP_RE.match(s or "")
    return m.group(1) if m else ""


def maven_update_mode(s: str) -> Dict[str, Any]:
    return {
        "is_prop_ref": maven_is_property_ref(s),
        "prop_name": maven_prop_name(s),
    }


# ====================================================================
# Dependency helpers (deps_updater role)
# ====================================================================
def maven_normalize_desired(raw: Dict[str, Any]) -> Dict[str, str]:
    """
    Normalize desired map:
      - lower-case keys
      - stringify & trim values
      - drop empty values
    Supports keys 'artifactId' or 'groupId:artifactId'.
    """
    out: Dict[str, str] = {}
    for k, v in (raw or {}).items():
        if v is None:
            continue
        key = str(k).strip().lower()
        val = str(v).strip()
        if not key or not val:
            continue
        out[key] = val
    return out


def _to_list(matches: Any) -> List[str]:
    return xml_texts(matches)


def maven_dep_rows(artifact_ids: Any, group_ids: Any, versions: Any) -> List[Dict[str, str]]:
    """
    Build rows [{groupId, artifactId, version}] from three match lists.
    Raise on length mismatch to fail fast upstream.
    """
    arts = _to_list(artifact_ids)
    grps = _to_list(group_ids)
    vers = _to_list(versions)
    if not (len(arts) == len(grps) == len(vers)):
        raise ValueError(f"Dependency lists not aligned: art={len(arts)} grp={len(grps)} ver={len(vers)}")
    return [{"groupId": grps[i], "artifactId": arts[i], "version": vers[i]} for i in range(len(arts))]


def _lookup_keys(row: Dict[str, str]) -> List[str]:
    """
    Most-specific to least:
      1) 'groupId:artifactId'
      2) 'artifactId'
    All lowercased.
    """
    gid = (row.get("groupId") or "").strip().lower()
    aid = (row.get("artifactId") or "").strip().lower()
    keys: List[str] = []
    if gid and aid:
        keys.append(f"{gid}:{aid}")
    if aid:
        keys.append(aid)
    return keys


def maven_enforce_plan(rows: List[Dict[str, str]], desired: Dict[str, str], mode: str = "literal") -> List[Dict[str, str]]:
    """
    Build update plan for dependency versions.
      - mode='literal': skip ${prop} versions (safe default)
      - mode='all'    : include property-backed versions (future use)
    Output items: {groupId, artifactId, current, desired}
    """
    plan: List[Dict[str, str]] = []
    desired = desired or {}

    for r in rows or []:
        cur = (r.get("version") or "").strip()
        if mode == "literal" and maven_is_property_ref(cur):
            continue

        desired_ver = ""
        for k in _lookup_keys(r):
            if k in desired:
                desired_ver = desired[k].strip()
                break
        if not desired_ver:
            continue
        if cur != desired_ver:
            plan.append({
                "groupId": r.get("groupId", ""),
                "artifactId": r.get("artifactId", ""),
                "current": cur,
                "desired": desired_ver,
            })
    return plan


# ====================================================================
# Plugin + Plugin Dependency helpers (plugin_updater roles)
# (Parse raw POM XML text; namespace-agnostic traversal)
# ====================================================================
def prop_name(value: str) -> str:
    """Compatibility alias used by older roles/filters."""
    return maven_prop_name(value)


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
        name = maven_prop_name(v)
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


# --- Namespace-agnostic ElementTree helpers ---
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
    """Yield <plugin> under <project>/<build>/<plugins> (namespace-agnostic)."""
    for child in list(root):
        if _nsless(child.tag) != "build":
            continue
        for b in list(child):
            if _nsless(b.tag) != "plugins":
                continue
            for plugin in list(b):
                if _nsless(plugin.tag) == "plugin":
                    yield plugin


def maven_plugins(pom_xml: str, props: Dict[str, str] | None = None) -> List[Dict[str, str]]:
    """
    Returns:
      [{'artifactId': 'maven-compiler-plugin', 'version': '3.5.1', 'source': 'explicit'|'property:<name>'|'none'}, ...]
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
      [{'plugin':'maven-surefire-plugin','artifactId':'surefire-junit47','version':'2.19.1','source':'explicit'|'property:<name>'|'none'}, ...]
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


# ====================================================================
# Registration
# ====================================================================
class FilterModule(object):
    def filters(self):
        return {
            # XML helpers
            "xml_texts": xml_texts,
            "xml_first_text": xml_first_text,
            "xml_has_any": xml_has_any,
            # Project helpers
            "maven_project_meta": maven_project_meta,
            "maven_desired_version": maven_desired_version,
            "maven_is_property_ref": maven_is_property_ref,
            "maven_prop_name": maven_prop_name,
            "maven_update_mode": maven_update_mode,
            # Dependency helpers
            "maven_normalize_desired": maven_normalize_desired,
            "maven_dep_rows": maven_dep_rows,
            "maven_enforce_plan": maven_enforce_plan,
            # Plugin + plugin-deps (ElementTree-based)
            "prop_name": prop_name,                # backward-compat alias
            "resolve_version": resolve_version,    # version resolver
            "maven_plugins": maven_plugins,
            "maven_plugin_deps": maven_plugin_deps,
        }