import xml.etree.ElementTree as ET

from ingest.versions import (
    VersionResolution,
    group_confidence,
    moniker_info,
    resolve_member_versions,
)


def _member(xml: str) -> ET.Element:
    return ET.fromstring(xml)


def _cs_signature(member: ET.Element) -> ET.Element:
    for sig in member.findall("MemberSignature"):
        if sig.get("Language") == "C#":
            return sig
    raise AssertionError("no C# MemberSignature in fixture")


def test_mscorlib_versions_map_to_netframework_monikers():
    member = _member("""
        <Member MemberName="X">
          <MemberSignature Language="C#" Value="public void X ();" />
          <AssemblyInfo>
            <AssemblyName>mscorlib</AssemblyName>
            <AssemblyVersion>1.0.5000.0</AssemblyVersion>
            <AssemblyVersion>2.0.0.0</AssemblyVersion>
            <AssemblyVersion>4.0.0.0</AssemblyVersion>
          </AssemblyInfo>
        </Member>
    """)
    resolution = resolve_member_versions(member, _cs_signature(member))
    assert resolution.confidence == "inferred"
    assert set(resolution.monikers) == {
        "netframework-1.1",
        "netframework-2.0",
        "netframework-4.x",
    }


def test_netstandard_versions_map_directly():
    member = _member("""
        <Member MemberName="X">
          <MemberSignature Language="C#" Value="public void X ();" />
          <AssemblyInfo>
            <AssemblyName>netstandard</AssemblyName>
            <AssemblyVersion>2.0.0.0</AssemblyVersion>
            <AssemblyVersion>2.1.0.0</AssemblyVersion>
          </AssemblyInfo>
        </Member>
    """)
    resolution = resolve_member_versions(member, _cs_signature(member))
    assert set(resolution.monikers) == {"netstandard-2.0", "netstandard-2.1"}


def test_system_runtime_4x_is_netcore_legacy_5_and_above_is_net_nx():
    member = _member("""
        <Member MemberName="X">
          <MemberSignature Language="C#" Value="public void X ();" />
          <AssemblyInfo>
            <AssemblyName>System.Runtime</AssemblyName>
            <AssemblyVersion>4.2.2.0</AssemblyVersion>
            <AssemblyVersion>6.0.0.0</AssemblyVersion>
          </AssemblyInfo>
        </Member>
    """)
    resolution = resolve_member_versions(member, _cs_signature(member))
    assert set(resolution.monikers) == {"netcore-legacy", "net-6.0"}


def test_unmapped_assembly_name_contributes_nothing():
    member = _member("""
        <Member MemberName="X">
          <MemberSignature Language="C#" Value="public void X ();" />
          <AssemblyInfo>
            <AssemblyName>Some.Other.Assembly</AssemblyName>
            <AssemblyVersion>1.0.0.0</AssemblyVersion>
          </AssemblyInfo>
        </Member>
    """)
    resolution = resolve_member_versions(member, _cs_signature(member))
    assert resolution == VersionResolution(monikers=[], confidence="unknown")


def test_member_without_any_signal_is_unknown():
    member = _member("""
        <Member MemberName="X">
          <MemberSignature Language="C#" Value="public void X ();" />
        </Member>
    """)
    resolution = resolve_member_versions(member, _cs_signature(member))
    assert resolution == VersionResolution(monikers=[], confidence="unknown")


def test_framework_alternate_on_cs_signature_is_explicit_and_wins_over_assemblyinfo():
    member = _member("""
        <Member MemberName="X">
          <MemberSignature Language="C#" Value="public void X ();"
                            FrameworkAlternate="net-8.0;net-9.0" />
          <AssemblyInfo>
            <AssemblyName>System.Runtime</AssemblyName>
            <AssemblyVersion>6.0.0.0</AssemblyVersion>
          </AssemblyInfo>
        </Member>
    """)
    resolution = resolve_member_versions(member, _cs_signature(member))
    assert resolution.confidence == "explicit"
    assert set(resolution.monikers) == {"net-8.0", "net-9.0"}


def test_group_confidence_takes_the_best_across_overloads():
    assert group_confidence(
        [
            VersionResolution(monikers=[], confidence="unknown"),
            VersionResolution(monikers=["net-8.0"], confidence="inferred"),
        ]
    ) == "inferred"
    assert group_confidence(
        [
            VersionResolution(monikers=["net-8.0"], confidence="inferred"),
            VersionResolution(monikers=["net-9.0"], confidence="explicit"),
        ]
    ) == "explicit"
    assert group_confidence([]) == "unknown"


def test_moniker_info_for_fixed_and_dynamic_net_monikers():
    assert moniker_info("netframework-4.x") == (".NET Framework 4.x", "netframework", 2)
    label, family, sort_order = moniker_info("net-12.0")
    assert label == ".NET 12"
    assert family == "netcore"
    assert sort_order == 112


def test_moniker_info_never_crashes_on_an_unrecognized_moniker():
    # Observé sur le corpus complet : une valeur FrameworkAlternate réelle
    # ("netframework-4", sans ".x") qui ne correspond ni à la table connue
    # ni au format net-N.0 attendu — moniker_info doit rester défensive.
    assert moniker_info("netframework-4") == ("netframework-4", "unknown", 999)
    assert moniker_info("net-") == ("net-", "unknown", 999)
    assert moniker_info("net-abc") == ("net-abc", "unknown", 999)
