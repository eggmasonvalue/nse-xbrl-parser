import pytest
from nse_xbrl_parser import parse_xbrl_file

def test_parse_xbrl_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_xbrl_file("does_not_exist.xml")

def test_parse_xbrl_file_invalid_schema_ref(tmp_path):
    # Create a dummy XML with no schemaRef
    dummy_xml = tmp_path / "dummy.xml"
    dummy_xml.write_text("<xbrl></xbrl>")
    
    with pytest.raises(ValueError, match="Could not detect schemaRef"):
        parse_xbrl_file(dummy_xml)

def test_parse_xbrl_file_unsupported_schema(tmp_path):
    # XML with a fake schemaRef
    dummy_xml = tmp_path / "dummy.xml"
    dummy_xml.write_text('<xbrl><link:schemaRef href="fake-schema-2099-01-01.xsd"/></xbrl>')
    
    with pytest.raises(FileNotFoundError, match="found in the bundled taxonomy archive"):
        parse_xbrl_file(dummy_xml)

def test_parse_xbrl_file_with_archive_scoped_fraud_taxonomy(tmp_path):
    filing = tmp_path / "fraud_case.xml"
    filing.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:in-capmkt="https://www.sebi.gov.in/xbrl/2024-02-29/in-capmkt" xmlns:in-capmkt-ent="https://www.sebi.gov.in/xbrl/Announcement_For_Fraud_Or_Default/2024-02-29/in-capmkt/in-capmkt-ent" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xbrli="http://www.xbrl.org/2003/instance">
  <link:schemaRef xlink:type="simple" xlink:href="in-capmkt-ent-2024-02-29.xsd"/>
  <xbrli:context id="MainI">
    <xbrli:entity>
      <xbrli:identifier scheme="https://www.sebi.gov.in/in-capmkt/ScripCode">543386</xbrli:identifier>
    </xbrli:entity>
    <xbrli:period>
      <xbrli:instant>2026-03-02</xbrli:instant>
    </xbrli:period>
  </xbrli:context>
  <in-capmkt:NameOfTheCompany contextRef="MainI">Fino Payments Bank Limited</in-capmkt:NameOfTheCompany>
  <in-capmkt:NSESymbol contextRef="MainI">FINOPB</in-capmkt:NSESymbol>
</xbrli:xbrl>
""",
        encoding="utf-8",
    )

    facts = parse_xbrl_file(filing)

    assert facts["Name of the company"] == "Fino Payments Bank Limited"
    assert facts.get("NSE symbol", facts.get("NSE Symbol", facts.get("Nsesymbol"))) == "FINOPB"

def test_parse_qip_listing_includes_allottee_category_fields(tmp_path):
    filing = tmp_path / "qip_case.xml"
    filing.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:in-capmkt="https://www.sebi.gov.in/xbrl/2022-06-30/in-capmkt" xmlns:in-capmkt-ent="https://www.sebi.gov.in/xbrl/QIP_Listing/2022-06-30/in-capmkt/in-capmkt-ent" xmlns:in-capmkt-types="https://www.sebi.gov.in/xbrl/2022-06-30/in-capmkt-types" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xbrldi="http://xbrl.org/2006/xbrldi">
  <link:schemaRef xlink:href="in-capmkt-ent-2022-06-30.xsd" xlink:type="simple"/>
  <xbrli:context id="MainI">
    <xbrli:entity><xbrli:identifier scheme="https://www.sebi.gov.in/in-capmkt/ScripCode">539042</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2026-03-11</xbrli:instant></xbrli:period>
  </xbrli:context>
  <xbrli:context id="MainD">
    <xbrli:entity><xbrli:identifier scheme="https://www.sebi.gov.in/in-capmkt/ScripCode">539042</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2026-03-11</xbrli:startDate><xbrli:endDate>2026-03-11</xbrli:endDate></xbrli:period>
  </xbrli:context>
  <xbrli:context id="D_Allottees1">
    <xbrli:entity><xbrli:identifier scheme="https://www.sebi.gov.in/in-capmkt/ScripCode">539042</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:startDate>2026-03-11</xbrli:startDate><xbrli:endDate>2026-03-11</xbrli:endDate></xbrli:period>
    <xbrli:scenario><xbrldi:typedMember dimension="in-capmkt:AllotteesAxis"><in-capmkt:AllotteesDomain>AllotteesDomain1</in-capmkt:AllotteesDomain></xbrldi:typedMember></xbrli:scenario>
  </xbrli:context>
  <xbrli:context id="I_Allottees1">
    <xbrli:entity><xbrli:identifier scheme="https://www.sebi.gov.in/in-capmkt/ScripCode">539042</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2026-03-11</xbrli:instant></xbrli:period>
    <xbrli:scenario><xbrldi:typedMember dimension="in-capmkt:AllotteesAxis"><in-capmkt:AllotteesDomain>AllotteesDomain1</in-capmkt:AllotteesDomain></xbrldi:typedMember></xbrli:scenario>
  </xbrli:context>
  <xbrli:unit id="shares"><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unit>
  <xbrli:unit id="pure"><xbrli:measure>xbrli:pure</xbrli:measure></xbrli:unit>
  <xbrli:unit id="INRPerShare"><xbrli:divide><xbrli:unitNumerator><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unitNumerator><xbrli:unitDenominator><xbrli:measure>xbrli:shares</xbrli:measure></xbrli:unitDenominator></xbrli:divide></xbrli:unit>
  <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>
  <in-capmkt:NameOfTheCompany contextRef="MainI">AGI INFRA LIMTED</in-capmkt:NameOfTheCompany>
  <in-capmkt:ISIN contextRef="MainI">INE976R01033</in-capmkt:ISIN>
  <in-capmkt:CorporateIdentityNumber contextRef="MainD">L45200PB2005PLC028466</in-capmkt:CorporateIdentityNumber>
  <in-capmkt:ScripCode contextRef="MainI">539042</in-capmkt:ScripCode>
  <in-capmkt:NSESymbol contextRef="MainI">AGIIL</in-capmkt:NSESymbol>
  <in-capmkt:RelavantDate contextRef="MainI">2026-03-02</in-capmkt:RelavantDate>
  <in-capmkt:MinimumIssuePricePerUnit contextRef="MainD" decimals="INF" unitRef="INRPerShare">274.83</in-capmkt:MinimumIssuePricePerUnit>
  <in-capmkt:DateOfBIDOpening contextRef="MainI">2026-03-04</in-capmkt:DateOfBIDOpening>
  <in-capmkt:DateOfBIDClosing contextRef="MainI">2026-03-09</in-capmkt:DateOfBIDClosing>
  <in-capmkt:DateOfAllotmentOfShares contextRef="MainD">2026-03-10</in-capmkt:DateOfAllotmentOfShares>
  <in-capmkt:DiscountPerSharesAvailed contextRef="MainD" decimals="INF" unitRef="INRPerShare">9.83</in-capmkt:DiscountPerSharesAvailed>
  <in-capmkt:IssuePricePerUnit contextRef="MainD" decimals="INF" unitRef="pure">265</in-capmkt:IssuePricePerUnit>
  <in-capmkt:NumberOfSharesAllotted contextRef="MainI" decimals="INF" unitRef="shares">2830188</in-capmkt:NumberOfSharesAllotted>
  <in-capmkt:FinalAmountOfIssueSize contextRef="MainD" decimals="-7" unitRef="INR">750000000</in-capmkt:FinalAmountOfIssueSize>
  <in-capmkt:NumberOfAllottees contextRef="MainD" decimals="INF" unitRef="pure">1</in-capmkt:NumberOfAllottees>
  <in-capmkt:NumberOfEquitySharesListed contextRef="MainI" decimals="INF" unitRef="shares">2830188</in-capmkt:NumberOfEquitySharesListed>
  <in-capmkt:DateOfSubmission contextRef="MainI">2026-03-11</in-capmkt:DateOfSubmission>
  <in-capmkt:NameOfAllottees contextRef="D_Allottees1">CRAFT EMERGING MARKET FUND PCC - ELITE CAPITAL FUND</in-capmkt:NameOfAllottees>
  <in-capmkt:NumberOfSharesAllotted contextRef="I_Allottees1" decimals="INF" unitRef="shares">660000</in-capmkt:NumberOfSharesAllotted>
  <in-capmkt:PercentageOfTotalIssueSize contextRef="D_Allottees1" decimals="INF" unitRef="pure">0.2332</in-capmkt:PercentageOfTotalIssueSize>
  <in-capmkt:CategoryOfAllotees contextRef="D_Allottees1">Foreign Portfolio Investor</in-capmkt:CategoryOfAllotees>
</xbrli:xbrl>
""",
        encoding="utf-8",
    )

    facts = parse_xbrl_file(filing)

    assert facts["Category of allotees"] == "Foreign Portfolio Investor"
    assert facts["Percentage of total issue size"] == "0.2332"
    assert facts["Date of BID opening"] == "2026-03-04"
    assert facts["Relavant date"] == "2026-03-02"
