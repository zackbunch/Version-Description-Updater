# filter_plugins/pom_filters.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Any, Dict, List

# Regex for ${property.name}
_PROP_RE = re.compile(r"^\s*\$\{([^}]+)\}\s*$")

# --------------------------------------------------------------------
# XML helpers
# --------------------------------------------------------------------
def xml_texts(matches: Any) -> List[str]:
    """
    Flatten community.general.xml 'matches' output to a list of trimmed strings.
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


# --------------------------------------------------------------------
# Maven project helpers (for project_updater role)
# --------------------------------------------------------------------
def maven_project_meta(
    gid_matches: Any,
    aid_matches: Any,
    ver_any_matches: Any,
    ver_direct_matches: Any,
) -> Dict[str, Any]:
    """
    Return a normalized dict of {groupId, artifactId, version, has_direct_version}.
    """
    return {
        "groupId": xml_first_text(gid_matches),
        "artifactId": xml_first_text(aid_matches),
        "version": xml_first_text(ver_any_matches),
        "has_direct_version": len(xml_texts(ver_direct_matches)) > 0,
    }


def maven_desired_version(app_map: Dict[str, Any], group_id: str, artifact_id: str) -> str:
    """
    Lookup desired version from applications.json:
      Prefer 'groupId:artifactId', fallback to 'artifactId'.
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
    """True if the string is a ${property} reference."""
    return bool(_PROP_RE.match(s or ""))


def maven_prop_name(s: str) -> str:
    """Extract property name from ${prop}, or '' if not a property ref."""
    m = _PROP_RE.match(s or "")
    return m.group(1) if m else ""


def maven_update_mode(s: str) -> Dict[str, Any]:
    """Return a structured update mode dict used in the role."""
    return {
        "is_prop_ref": maven_is_property_ref(s),
        "prop_name": maven_prop_name(s),
    }


# --------------------------------------------------------------------
# Register filters
# --------------------------------------------------------------------
class FilterModule(object):
    def filters(self):
        return {
            "xml_texts": xml_texts,
            "xml_first_text": xml_first_text,
            "maven_project_meta": maven_project_meta,
            "maven_desired_version": maven_desired_version,
            "maven_is_property_ref": maven_is_property_ref,
            "maven_prop_name": maven_prop_name,
            "maven_update_mode": maven_update_mode,
        }