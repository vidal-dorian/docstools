from pathlib import Path

from ingest.examples import classify_example, measure_inline_examples
from ingest.parser import parse_type

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Les 5 types utilisés pour la mesure de la spec §4 (mapping de version) et
# §11 (proportion d'exemples inline) : même échantillon de 793 membres.
SAMPLE_FIXTURES = [
    "System.DateTime.xml",
    "System.String.xml",
    "System.Math.xml",
    "System.Collections.Generic.List`1.xml",
    "System.Linq.Enumerable.xml",
]


def test_no_remarks_is_none():
    assert classify_example(None) == "none"
    assert classify_example("") == "none"


def test_remarks_without_examples_heading_is_none():
    remarks = "## Remarks\nSome prose with a ```csharp\nvar x = 1;\n``` snippet, no Examples."
    assert classify_example(remarks) == "none"


def test_examples_heading_with_docfx_inclusion_is_external():
    remarks = """## Remarks
Some prose.

## Examples
The following example demonstrates the method.

:::code language="csharp" source="~/snippets/csharp/Sample.cs" id="Snippet1":::
"""
    assert classify_example(remarks) == "external"


def test_examples_heading_with_legacy_inclusion_is_external():
    remarks = """## Examples
[!code-csharp[Sample](~/samples/sample.cs)]
"""
    assert classify_example(remarks) == "external"


def test_examples_heading_with_fenced_code_is_inline():
    remarks = """## Examples
The following example is fully self-contained.

```csharp
var date = new DateTime(2024, 1, 1);
Console.WriteLine(date.AddMonths(1));
```
"""
    assert classify_example(remarks) == "inline"


def test_examples_heading_without_any_code_is_none():
    remarks = "## Examples\nNo code was ever added for this member."
    assert classify_example(remarks) == "none"


def test_inclusion_takes_priority_over_a_stray_fenced_block_in_the_same_section():
    # Cas réel observé (List<T>) : un extrait de signature en dehors de la
    # section Examples ne doit pas la faire compter comme inline si la
    # section Examples elle-même ne contient qu'une inclusion externe.
    remarks = """The delegate has the signature:

```csharp
public bool methodName(T obj)
```

## Examples
:::code language="csharp" source="~/snippets/csharp/Sample.cs" id="Snippet1":::
"""
    assert classify_example(remarks) == "external"


def test_measure_inline_examples_counts_across_types():
    xml_a = """
    <Type Name="A" FullName="Ns.A">
      <TypeSignature Language="C#" Value="public class A" />
      <Docs><summary>A.</summary></Docs>
      <Members>
        <Member MemberName="M1">
          <MemberSignature Language="C#" Value="public void M1 ();" />
          <MemberType>Method</MemberType>
          <Docs><summary>M1.</summary><remarks>
            <format type="text/markdown"><![CDATA[
## Examples
```csharp
DoThing();
```
]]></format>
          </remarks></Docs>
        </Member>
        <Member MemberName="M2">
          <MemberSignature Language="C#" Value="public void M2 ();" />
          <MemberType>Method</MemberType>
          <Docs><summary>M2.</summary><remarks>
            <format type="text/markdown"><![CDATA[
## Examples
:::code language="csharp" source="~/snippets/x.cs":::
]]></format>
          </remarks></Docs>
        </Member>
        <Member MemberName="M3">
          <MemberSignature Language="C#" Value="public void M3 ();" />
          <MemberType>Method</MemberType>
          <Docs><summary>M3.</summary></Docs>
        </Member>
      </Members>
    </Type>
    """
    parsed = parse_type(xml_a)
    counts = measure_inline_examples([parsed])
    assert counts == {"inline": 1, "external": 1, "none": 1}


def test_real_sample_of_793_members_has_zero_percent_inline_examples():
    # Reproduit la mesure consignée dans docs/specification.md §11 : sur
    # l'échantillon officiel de 793 membres (DateTime, String, Math, List<T>,
    # Enumerable), dotnet-api-docs n'a plus aucun exemple réellement inline —
    # tous les blocs "## Examples" renvoient vers ~/snippets/... (US-014).
    parsed_types = [
        parse_type((FIXTURES_DIR / name).read_text(encoding="utf-8")) for name in SAMPLE_FIXTURES
    ]
    total_overloads = sum(len(g.overloads) for t in parsed_types for g in t.groups)
    counts = measure_inline_examples(parsed_types)

    assert total_overloads == 793
    assert counts["inline"] == 0
    assert counts["external"] == 395
    assert counts["none"] == 398
