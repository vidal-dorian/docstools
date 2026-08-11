"""Résolution du moniker de version depuis `<AssemblyInfo>` / `FrameworkAlternate` (US-012).

Voir docs/specification.md, section 4 « Résolution des versions ». Le signal
principal est `<AssemblyInfo>` (`AssemblyName` + `AssemblyVersion`) : c'est le
cas très majoritaire (`inferred`). `FrameworkAlternate` sur la signature C#
est rare mais prioritaire quand présent (`explicit`). En dernier recours,
`unknown` — le membre est alors considéré présent sur toutes les versions
par l'algorithme de recherche (spec §5), sans ligne `overload_version`.
"""

from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass

_CONFIDENCE_RANK = {"unknown": 0, "inferred": 1, "explicit": 2}

# moniker -> (label, family, sort_order) — voir spec §4, tableau de mapping.
_FIXED_MONIKERS: dict[str, tuple[str, str, int]] = {
    "netframework-1.1": (".NET Framework 1.1", "netframework", 0),
    "netframework-2.0": (".NET Framework 2.0 – 3.5", "netframework", 1),
    "netframework-4.x": (".NET Framework 4.x", "netframework", 2),
    "netstandard-2.0": (".NET Standard 2.0", "netstandard", 3),
    "netstandard-2.1": (".NET Standard 2.1", "netstandard", 4),
    "netcore-legacy": (".NET Core 1.0 – 3.1", "netcore", 5),
}


@dataclass
class VersionResolution:
    monikers: list[str]
    confidence: str  # explicit | inferred | unknown


def resolve_member_versions(
    member: ET.Element, cs_signature: ET.Element | None
) -> VersionResolution:
    """Dérive les monikers disponibles pour un `<Member>` et le niveau de
    confiance associé (spec §4)."""
    framework_alternate = (
        cs_signature.get("FrameworkAlternate") if cs_signature is not None else None
    )
    if framework_alternate:
        monikers = [m.strip() for m in framework_alternate.split(";") if m.strip()]
        return VersionResolution(monikers=monikers, confidence="explicit")

    monikers: set[str] = set()
    for assembly_info in member.findall("AssemblyInfo"):
        assembly_name = assembly_info.findtext("AssemblyName", default="")
        for version_elem in assembly_info.findall("AssemblyVersion"):
            moniker = _assembly_version_moniker(assembly_name, (version_elem.text or "").strip())
            if moniker:
                monikers.add(moniker)

    if monikers:
        return VersionResolution(monikers=sorted(monikers), confidence="inferred")

    # Règle de repli (spec §4) : aucun signal exploitable.
    return VersionResolution(monikers=[], confidence="unknown")


def group_confidence(resolutions: list[VersionResolution]) -> str:
    """Confiance d'un `member_group` : la meilleure confiance parmi ses surcharges."""
    if not resolutions:
        return "unknown"
    return max((r.confidence for r in resolutions), key=_CONFIDENCE_RANK.__getitem__)


def _assembly_version_moniker(assembly_name: str, version: str) -> str | None:
    parts = version.split(".")
    if not parts or not parts[0].isdigit():
        return None
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

    if assembly_name == "mscorlib":
        if version == "1.0.5000.0":
            return "netframework-1.1"
        if major == 2:
            return "netframework-2.0"
        if major == 4:
            return "netframework-4.x"
        return None
    if assembly_name == "netstandard":
        if major == 2 and minor == 0:
            return "netstandard-2.0"
        if major == 2 and minor == 1:
            return "netstandard-2.1"
        return None
    if assembly_name == "System.Runtime":
        if major == 4:
            return "netcore-legacy"
        if major >= 5:
            return f"net-{major}.0"
        return None
    return None


def moniker_info(moniker: str) -> tuple[str, str, int]:
    """`(label, family, sort_order)` pour une entrée de la table `version`."""
    if moniker in _FIXED_MONIKERS:
        return _FIXED_MONIKERS[moniker]

    net_major = moniker.removeprefix("net-").split(".")[0]
    if moniker.startswith("net-") and net_major.isdigit():
        major = int(net_major)
        return (f".NET {major}", "netcore", 100 + major)

    # Moniker inattendu : les valeurs `FrameworkAlternate` (confiance
    # 'explicit') viennent telles quelles du XML source et ne suivent pas
    # toujours la table connue ni le format net-N.0 (ex. "netframework-4"
    # sans ".x", observé sur le corpus complet). Pas de métadonnées
    # connues, mais on ne doit jamais planter le build pour autant.
    return (moniker, "unknown", 999)


def get_or_create_version(conn: sqlite3.Connection, source_id: int, moniker: str) -> int:
    row = conn.execute(
        "SELECT id FROM version WHERE source_id = ? AND moniker = ?", (source_id, moniker)
    ).fetchone()
    if row is not None:
        return row[0]
    label, family, sort_order = moniker_info(moniker)
    cursor = conn.execute(
        "INSERT INTO version (source_id, moniker, label, family, sort_order) "
        "VALUES (?, ?, ?, ?, ?)",
        (source_id, moniker, label, family, sort_order),
    )
    return cursor.lastrowid
