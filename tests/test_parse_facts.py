from pathlib import Path

from nse_xbrl_parser import parse_xbrl_facts


def _write_multi_context_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "multi_context_qip.xml"
    fixture.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
  xmlns:xbrli="http://www.xbrl.org/2003/instance"
  xmlns:in-capmkt="https://www.sebi.gov.in/xbrl/2022-06-30/in-capmkt"
  xmlns:in-capmkt-ent="https://www.sebi.gov.in/xbrl/QIP_Listing/2022-06-30/in-capmkt/in-capmkt-ent"
  xmlns:in-capmkt-types="https://www.sebi.gov.in/xbrl/2022-06-30/in-capmkt-types"
  xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
  xmlns:link="http://www.xbrl.org/2003/linkbase"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
>
  <link:schemaRef xlink:href="in-capmkt-ent-2022-06-30.xsd" xlink:type="simple"/>

  <xbrli:context id="MainI">
    <xbrli:entity>
      <xbrli:identifier scheme="https://www.sebi.gov.in/in-capmkt/ScripCode">539042</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2026-03-11</xbrli:instant>
    </xbrli:period>
  </xbrli:context>

  <xbrli:context id="MainD">
    <xbrli:entity>
      <xbrli:identifier scheme="https://www.sebi.gov.in/in-capmkt/ScripCode">539042</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:startDate>2026-01-01</xbrli:startDate>
      <xbrli:endDate>2026-03-31</xbrli:endDate>
    </xbrli:period>
  </xbrli:context>

  <xbrli:context id="I_Standalone">
    <xbrli:entity>
      <xbrli:identifier scheme="https://www.sebi.gov.in/in-capmkt/ScripCode">539042</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2026-03-11</xbrli:instant>
    </xbrli:period>
    <xbrli:scenario>
      <xbrldi:typedMember dimension="in-capmkt:AllotteesAxis">
        <in-capmkt:AllotteesDomain>StandaloneMember</in-capmkt:AllotteesDomain>
      </xbrldi:typedMember>
    </xbrli:scenario>
  </xbrli:context>

  <xbrli:context id="I_Consolidated">
    <xbrli:entity>
      <xbrli:identifier scheme="https://www.sebi.gov.in/in-capmkt/ScripCode">539042</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2026-03-11</xbrli:instant>
    </xbrli:period>
    <xbrli:scenario>
      <xbrldi:typedMember dimension="in-capmkt:AllotteesAxis">
        <in-capmkt:AllotteesDomain>ConsolidatedMember</in-capmkt:AllotteesDomain>
      </xbrldi:typedMember>
    </xbrli:scenario>
  </xbrli:context>

  <xbrli:unit id="shares"><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>
  <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>

  <in-capmkt:NumberOfSharesAllotted contextRef="MainI" decimals="INF" unitRef="shares">1000</in-capmkt:NumberOfSharesAllotted>
  <in-capmkt:NumberOfSharesAllotted contextRef="I_Standalone" decimals="INF" unitRef="shares">600</in-capmkt:NumberOfSharesAllotted>
  <in-capmkt:NumberOfSharesAllotted contextRef="I_Consolidated" decimals="INF" unitRef="shares">400</in-capmkt:NumberOfSharesAllotted>
  <in-capmkt:FinalAmountOfIssueSize contextRef="MainD" decimals="-3" unitRef="INR">15000000</in-capmkt:FinalAmountOfIssueSize>
  <in-capmkt:CategoryOfAllotees contextRef="I_Standalone" xsi:nil="true"/>
</xbrli:xbrl>
""",
        encoding="utf-8",
    )
    return fixture


def test_parse_xbrl_facts_preserves_context_dimensions_and_periods(tmp_path):
    fixture = _write_multi_context_fixture(tmp_path)

    rows = parse_xbrl_facts(fixture)

    assert rows

    first_row = rows[0]
    assert {
        "concept",
        "value",
        "unit",
        "decimals",
        "period",
        "context_id",
        "dimensions",
        "basis",
        "entity",
        "is_nil",
        "is_tuple",
    }.issubset(first_row.keys())

    shares_rows = [
        row for row in rows if row["concept"]["local_name"] == "NumberOfSharesAllotted"
    ]
    assert len(shares_rows) == 3
    assert {row["context_id"] for row in shares_rows} == {
        "MainI",
        "I_Standalone",
        "I_Consolidated",
    }

    main_row = next(row for row in shares_rows if row["context_id"] == "MainI")
    standalone_row = next(
        row for row in shares_rows if row["context_id"] == "I_Standalone"
    )
    consolidated_row = next(
        row for row in shares_rows if row["context_id"] == "I_Consolidated"
    )

    assert str(main_row["period"].get("instant", "")).startswith("2026-03-11")
    assert main_row["dimensions"] == {}
    assert main_row["basis"] is None

    standalone_dims = standalone_row["dimensions"]
    assert len(standalone_dims) == 1
    assert any(key.endswith(":AllotteesAxis") for key in standalone_dims)
    assert "StandaloneMember" in next(iter(standalone_dims.values()))
    assert standalone_row["basis"] == "standalone"

    consolidated_dims = consolidated_row["dimensions"]
    assert len(consolidated_dims) == 1
    assert any(key.endswith(":AllotteesAxis") for key in consolidated_dims)
    assert "ConsolidatedMember" in next(iter(consolidated_dims.values()))
    assert consolidated_row["basis"] == "consolidated"

    duration_row = next(
        row for row in rows if row["concept"]["local_name"] == "FinalAmountOfIssueSize"
    )
    assert str(duration_row["period"]["start"]).startswith("2026-01-01")
    assert str(duration_row["period"]["end"]).startswith("2026-03-31")

    assert duration_row["entity"] == {
        "scheme": "https://www.sebi.gov.in/in-capmkt/ScripCode",
        "identifier": "539042",
    }

    nil_row = next(
        row for row in rows if row["concept"]["local_name"] == "CategoryOfAllotees"
    )
    assert nil_row["is_nil"] is True
    assert nil_row["value"] is None


def test_parse_xbrl_facts_supports_rpt_2022_http_taxonomy_namespace(tmp_path):
    fixture = tmp_path / "rpt_2022_http_namespace.xml"
    fixture.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl
  xmlns:xbrli="http://www.xbrl.org/2003/instance"
  xmlns:in-capmkt="http://www.sebi.gov.in/xbrl/2022-03-31/in-capmkt"
  xmlns:in-capmkt-roles="http://www.sebi.gov.in/xbrl/RelatedPartyTransactions/2022-03-31/in-capmkt/in-capmkt-ent"
  xmlns:in-capmkt-types="https://www.sebi.gov.in/xbrl/2022-03-31/in-capmkt-types"
  xmlns:link="http://www.xbrl.org/2003/linkbase"
  xmlns:xlink="http://www.w3.org/1999/xlink"
>
  <link:schemaRef xlink:href="in-capmkt-ent-2022-03-31.xsd" xlink:type="simple"/>

  <xbrli:context id="MainI">
    <xbrli:entity>
      <xbrli:identifier scheme="https://www.sebi.gov.in/in-capmkt/ScripCode">500325</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2022-09-30</xbrli:instant>
    </xbrli:period>
  </xbrli:context>

  <in-capmkt:NameOfTheCompany contextRef="MainI">Reliance Industries Limited</in-capmkt:NameOfTheCompany>
</xbrli:xbrl>
""",
        encoding="utf-8",
    )

    rows = parse_xbrl_facts(fixture)

    assert rows
    company_row = next(
        row for row in rows if row["concept"]["local_name"] == "NameOfTheCompany"
    )
    assert company_row["value"] == "Reliance Industries Limited"
    assert (
        company_row["concept"]["namespace"]
        == "http://www.sebi.gov.in/xbrl/2022-03-31/in-capmkt"
    )
