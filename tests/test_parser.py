import shutil
import subprocess
from pathlib import Path

import pytest

from nse_xbrl_parser import parse_xbrl_file


PREFERENTIAL_ISSUE_LISTING_URL = (
    "https://nsearchives.nseindia.com/corporate/xbrl/"
    "PREF_ISSUE_LS_1634111_10032026122945_WEB.xml"
)
FRAUD_DISCLOSURE_URL = (
    "https://nsearchives.nseindia.com/corporate/xbrl/"
    "Fraud_543386_232026114438_ANN_FRAUD_WebXMLFile_20260302_114440997.xml"
)
NOTICE_OF_SHAREHOLDERS_URL = (
    "https://nsearchives.nseindia.com/corporate/xbrl/"
    "NOTICE_OF_SHAREHOLDERS_MEETINGS_1630641_26022026110702_WEB.xml"
)
CIM_APPOINTMENT_URL = (
    "https://nsearchives.nseindia.com/corporate/xbrl/"
    "CIM_80184_1633670_08032026122822_WEB.xml"
)
ALTERATION_OF_CAPITAL_URL = (
    "https://nsearchives.nseindia.com/corporate/xbrl/"
    "ALTERATION_OF_CAPITAL_AND_FUND_RAISING_992794_30112023082854_WEB.xml"
)


def _download_with_curl(destination: Path, url: str):
    curl_bin = shutil.which("curl.exe") or shutil.which("curl")
    if not curl_bin:
        pytest.skip("curl is not available in the test environment.")

    result = subprocess.run(
        [
            curl_bin,
            "--http1.1",
            "-L",
            "--retry",
            "3",
            "--retry-all-errors",
            "--connect-timeout",
            "20",
            "--max-time",
            "180",
            "-A",
            "Mozilla/5.0",
            "-H",
            "Accept: application/xml,text/xml,*/*",
            url,
            "-o",
            str(destination),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(
            "Unable to fetch live NSE filing via curl: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )


def _fetch_live_filing(tmp_path, filename, url):
    path = tmp_path / filename
    _download_with_curl(path, url)
    return path

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


def test_parse_live_fraud_disclosure_from_nse_url(tmp_path):
    filing = _fetch_live_filing(tmp_path, "fraud_disclosure.xml", FRAUD_DISCLOSURE_URL)

    facts = parse_xbrl_file(filing)

    assert facts["Name of the company"] == "Fino Payments Bank Limited"
    assert facts["NSE symbol"] == "FINOPB"
    assert facts["Type of announcement"] == "New"
    assert facts["Date of report"] == "2026-03-02"


def test_parse_live_notice_of_shareholders_meeting(tmp_path):
    filing = _fetch_live_filing(
        tmp_path,
        "notice_of_shareholders_meeting.xml",
        NOTICE_OF_SHAREHOLDERS_URL,
    )

    facts = parse_xbrl_file(filing)

    assert facts["Name of the company"] == "Fino Payments Bank Limited"
    assert facts["NSE symbol"] == "FINOPB"
    assert facts["Type of announcement"] == "New"
    assert facts["Date of shareholders meeting"] == "2026-02-28"
    assert facts["Amount of remuneration"] == "56984704"
    assert facts["Event for notice of shareholders meeting"] == "Postal Ballot"
    assert facts["Mode of shareholders meeting"] == "Postal Ballot"


def test_parse_live_cim_appointment_details(tmp_path):
    filing = _fetch_live_filing(tmp_path, "cim_appointment.xml", CIM_APPOINTMENT_URL)

    facts = parse_xbrl_file(filing)

    assert facts["Name of the company"] == "FINO PAYMENTS BANK LIMITED"
    assert facts["NSE symbol"] == "FINOPB"
    assert facts["Designation"] == "Others"
    assert facts["Reason of change"] == "Appointment"
    assert (
        facts["Name of the person or auditor or audit firm or RTA"]
        == "Ketan Dhirendra Merchant"
    )


def test_parse_live_alteration_of_capital_and_fund_raising(tmp_path):
    filing = _fetch_live_filing(
        tmp_path,
        "alteration_of_capital.xml",
        ALTERATION_OF_CAPITAL_URL,
    )

    facts = parse_xbrl_file(filing)

    assert facts["Name of the company"] == "FINO PAYMENTS BANK LIMITED"
    assert facts["NSE symbol"] == "FINOPB"
    assert facts["Date of report"] == "2023-11-30"
    assert facts["Type of announcement"] == "Update"


def test_parse_live_preferential_issue_listing_from_nse_url(tmp_path):
    filing = _fetch_live_filing(
        tmp_path,
        "pref_issue_listing.xml",
        PREFERENTIAL_ISSUE_LISTING_URL,
    )

    facts = parse_xbrl_file(filing)

    assert facts["Name of the company"] == "Grill Splendour Services Limited"
    assert facts["NSE symbol"] == "BIRDYS"
    assert facts["Offer price per security"] == "85.61"
    assert facts["Date of allotment of shares"] == "2025-02-20"
    assert facts["Total number of shares allotted"] == "239745"
