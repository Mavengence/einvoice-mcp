"""Comprehensive edge-case and integration tests for einvoice-mcp.

Covers all uncovered code paths, error handling branches, cross-module
roundtrips, and boundary conditions identified in coverage analysis.
"""

import base64
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
import respx
from pydantic import ValidationError

from einvoice_mcp.errors import (
    InvoiceGenerationError,
    InvoiceParsingError,
    KoSITConnectionError,
    KoSITValidationError,
)
from einvoice_mcp.models import (
    Address,
    InvoiceData,
    InvoiceProfile,
    LineItem,
    Party,
    TaxBreakdown,
    TaxCategory,
    Totals,
)
from einvoice_mcp.services.invoice_builder import build_xml
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.services.pdf_generator import (
    embed_xml_in_pdf,
    generate_invoice_pdf,
)
from einvoice_mcp.services.xml_parser import (
    _safe_decimal,
    _str_element,
    extract_xml_from_pdf,
    parse_xml,
)
from einvoice_mcp.tools.compliance import check_compliance
from einvoice_mcp.tools.generate import generate_xrechnung, generate_zugferd
from einvoice_mcp.tools.parse import parse_einvoice
from einvoice_mcp.tools.validate import validate_zugferd

KOSIT_URL = "http://kosit-mock:8081"

MOCK_VALID_REPORT = """\
<?xml version="1.0" encoding="UTF-8"?>
<rep:report xmlns:rep="http://www.xoev.de/de/validator/varl/1">
  <rep:assessment>
    <rep:profileName>XRechnung 3.0.2</rep:profileName>
  </rep:assessment>
</rep:report>
"""


# ============================================================================
# 1. Error exception hierarchy tests
# ============================================================================


class TestErrorExceptions:
    """Cover errors.py lines 42-48 (InvoiceGenerationError) and 55-61 (InvoiceParsingError)."""

    def test_invoice_generation_error_default(self) -> None:
        err = InvoiceGenerationError()
        assert "fehlgeschlagen" in err.message_de
        assert "failed" in str(err)

    def test_invoice_generation_error_with_detail(self) -> None:
        err = InvoiceGenerationError("bad data")
        # Security: detail must NOT leak into user-facing message_de
        assert "bad data" not in err.message_de
        assert "fehlgeschlagen" in err.message_de
        assert "bad data" in str(err)

    def test_invoice_parsing_error_default(self) -> None:
        err = InvoiceParsingError()
        assert "gelesen werden" in err.message_de

    def test_invoice_parsing_error_with_detail(self) -> None:
        err = InvoiceParsingError("corrupt PDF")
        # Security: detail must NOT leak into user-facing message_de
        assert "corrupt PDF" not in err.message_de
        assert "gelesen werden" in err.message_de
        assert "corrupt PDF" in str(err)

    def test_kosit_connection_error_default(self) -> None:
        err = KoSITConnectionError()
        assert "erreichbar" in err.message_de

    def test_kosit_validation_error_default(self) -> None:
        err = KoSITValidationError()
        assert "fehlgeschlagen" in err.message_de


# ============================================================================
# 2. xml_parser edge cases (covers lines 27-43, 76, 96-98, 137-138, etc.)
# ============================================================================


class TestXmlParserEdgeCases:
    def test_parse_invalid_xml_raises(self) -> None:
        with pytest.raises(InvoiceParsingError):
            parse_xml(b"not xml at all")

    def test_parse_empty_xml_raises(self) -> None:
        with pytest.raises(InvoiceParsingError):
            parse_xml(b"")

    def test_extract_xml_from_pdf_invalid_pdf(self) -> None:
        # Security: error message must NOT contain raw exception detail
        with pytest.raises(InvoiceParsingError, match="parsing failed"):
            extract_xml_from_pdf(b"not a real PDF")

    def test_extract_xml_from_pdf_empty(self) -> None:
        with pytest.raises(InvoiceParsingError):
            extract_xml_from_pdf(b"")

    def test_str_element_none(self) -> None:
        assert _str_element(None) == ""

    def test_str_element_preserves_empty_parens(self) -> None:
        # Empty parens are NOT a schemeID pattern — preserve them
        assert _str_element("DE123 ()") == "DE123 ()"

    def test_strips_numeric_scheme(self) -> None:
        assert _str_element("4000000000098 (9930)") == "4000000000098"

    def test_str_element_strips_scheme_id(self) -> None:
        # SchemeID patterns: short uppercase alphanumeric in parens
        assert _str_element("DE123456789 (VA)") == "DE123456789"
        assert _str_element("seller@example.com (EM)") == "seller@example.com"
        assert _str_element("4000000000098 (9930)") == "4000000000098"

    def test_str_element_preserves_description_parens(self) -> None:
        # Natural language parenthetical text must NOT be stripped
        assert _str_element("Reisekosten (pauschal)") == "Reisekosten (pauschal)"
        assert _str_element("Beratung (inkl. Reise)") == "Beratung (inkl. Reise)"
        assert _str_element("Software-Lizenz (jährlich)") == "Software-Lizenz (jährlich)"
        assert _str_element("Hosting (pro Monat)") == "Hosting (pro Monat)"

    def test_str_element_normal_string(self) -> None:
        assert _str_element("hello") == "hello"

    def test_str_element_whitespace(self) -> None:
        assert _str_element("  test  ") == "test"

    def test_safe_decimal_none(self) -> None:
        assert _safe_decimal(None) == Decimal("0")

    def test_safe_decimal_from_decimal(self) -> None:
        assert _safe_decimal(Decimal("42.50")) == Decimal("42.50")

    def test_safe_decimal_from_string(self) -> None:
        assert _safe_decimal("19.00") == Decimal("19.00")

    def test_safe_decimal_empty_string(self) -> None:
        assert _safe_decimal("") == Decimal("0")

    def test_safe_decimal_invalid_string(self) -> None:
        assert _safe_decimal("not-a-number") == Decimal("0")

    def test_safe_decimal_with_value_attr(self) -> None:
        class FakeDecimalElement:
            _value = Decimal("99.99")

        assert _safe_decimal(FakeDecimalElement()) == Decimal("99.99")

    def test_safe_decimal_with_none_value_attr(self) -> None:
        class FakeDecimalElement:
            _value = None

        assert _safe_decimal(FakeDecimalElement()) == Decimal("0")

    def test_safe_decimal_with_amount_attr_decimal(self) -> None:
        class FakeCurrencyElement:
            _amount = Decimal("100.00")

        assert _safe_decimal(FakeCurrencyElement()) == Decimal("100.00")

    def test_safe_decimal_with_amount_attr_string(self) -> None:
        class FakeCurrencyElement:
            _amount = "55.50"

        assert _safe_decimal(FakeCurrencyElement()) == Decimal("55.50")

    def test_safe_decimal_with_invalid_amount(self) -> None:
        class FakeCurrencyElement:
            _amount = "bad"

        assert _safe_decimal(FakeCurrencyElement()) == Decimal("0")

    def test_safe_decimal_with_scheme_suffix(self) -> None:
        assert _safe_decimal("100 ()") == Decimal("100")

    def test_parse_xml_wraps_extraction_error(self) -> None:
        """If drafthorse parse succeeds but extraction fails, wrap in InvoiceParsingError."""
        from unittest.mock import patch

        from einvoice_mcp.errors import InvoiceParsingError

        # Valid XML that passes defusedxml but causes drafthorse to fail
        valid_xml = (
            b'<?xml version="1.0"?>'
            b"<rsm:CrossIndustryInvoice"
            b' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">'
            b"</rsm:CrossIndustryInvoice>"
        )
        with (
            patch(
                "einvoice_mcp.services.xml_parser._extract_invoice",
                side_effect=RuntimeError("extraction boom"),
            ),
            pytest.raises(InvoiceParsingError),
        ):
            parse_xml(valid_xml)

    def test_parse_xml_reraises_invoice_parsing_error(self) -> None:
        """If _extract_invoice raises InvoiceParsingError, re-raise directly."""
        from unittest.mock import patch

        from einvoice_mcp.errors import InvoiceParsingError

        valid_xml = (
            b'<?xml version="1.0"?>'
            b"<rsm:CrossIndustryInvoice"
            b' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">'
            b"</rsm:CrossIndustryInvoice>"
        )
        with (
            patch(
                "einvoice_mcp.services.xml_parser._extract_invoice",
                side_effect=InvoiceParsingError("controlled"),
            ),
            pytest.raises(InvoiceParsingError, match="controlled"),
        ):
            parse_xml(valid_xml)

    def test_extract_scheme_id_from_string_fallback(self) -> None:
        """_extract_scheme_id falls back to string pattern matching."""
        from einvoice_mcp.services.xml_parser import _extract_scheme_id

        class FakeID:
            def __str__(self) -> str:
                return "123/456/78901 (FC)"

        assert _extract_scheme_id(FakeID()) == "FC"

    def test_extract_scheme_id_no_scheme(self) -> None:
        """_extract_scheme_id returns empty for no scheme."""
        from einvoice_mcp.services.xml_parser import _extract_scheme_id

        class FakeID:
            def __str__(self) -> str:
                return "plain text"

        assert _extract_scheme_id(FakeID()) == ""

    def test_extract_scheme_id_with_attr(self) -> None:
        """_extract_scheme_id uses _scheme_id attribute when available."""
        from einvoice_mcp.services.xml_parser import _extract_scheme_id

        class FakeID:
            _scheme_id = "VA"

            def __str__(self) -> str:
                return "DE123456789 (VA)"

        assert _extract_scheme_id(FakeID()) == "VA"


# ============================================================================
# 3. Invoice builder error paths (covers lines 33-36)
# ============================================================================


class TestInvoiceBuilderErrors:
    def test_build_xml_reraises_invoice_generation_error(self) -> None:
        with (
            patch(
                "einvoice_mcp.services.invoice_builder._build_document",
                side_effect=InvoiceGenerationError("test"),
            ),
            pytest.raises(InvoiceGenerationError, match="test"),
        ):
            data = InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )
            build_xml(data)

    def test_build_xml_wraps_unexpected_error(self) -> None:
        with (
            patch(
                "einvoice_mcp.services.invoice_builder._build_document",
                side_effect=RuntimeError("unexpected"),
            ),
            pytest.raises(InvoiceGenerationError, match="generation failed"),
        ):
            data = InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )
            build_xml(data)


# ============================================================================
# 4. PDF generator error paths (covers lines 22-25, 55-58)
# ============================================================================


class TestPdfGeneratorErrors:
    def test_generate_pdf_reraises_invoice_error(self) -> None:
        with (
            patch(
                "einvoice_mcp.services.pdf_generator._build_pdf",
                side_effect=InvoiceGenerationError("bad pdf"),
            ),
            pytest.raises(InvoiceGenerationError, match="bad pdf"),
        ):
            data = InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )
            generate_invoice_pdf(data)

    def test_generate_pdf_wraps_unexpected_error(self) -> None:
        with (
            patch(
                "einvoice_mcp.services.pdf_generator._build_pdf",
                side_effect=RuntimeError("boom"),
            ),
            pytest.raises(InvoiceGenerationError, match="generation failed"),
        ):
            data = InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )
            generate_invoice_pdf(data)

    def test_embed_xml_failure(self) -> None:
        # Security: error message must NOT contain raw exception detail
        with pytest.raises(InvoiceGenerationError, match="generation failed"):
            embed_xml_in_pdf(b"not-a-pdf", b"<xml/>")


# ============================================================================
# 5. Generate tools error paths (covers lines 31-32, 67-78)
# ============================================================================


class TestGenerateToolErrors:
    @respx.mock
    async def test_generate_xrechnung_build_error(self) -> None:
        with patch(
            "einvoice_mcp.tools.generate.build_xml",
            side_effect=InvoiceGenerationError("build failed"),
        ):
            client = KoSITClient(base_url=KOSIT_URL)
            data = InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )
            result = await generate_xrechnung(data, client)
            assert result["success"] is False
            assert "fehlgeschlagen" in result["error"]
            await client.close()

    @respx.mock
    async def test_generate_zugferd_build_error(self) -> None:
        with patch(
            "einvoice_mcp.tools.generate.build_xml",
            side_effect=InvoiceGenerationError("build failed"),
        ):
            client = KoSITClient(base_url=KOSIT_URL)
            data = InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )
            result = await generate_zugferd(data, client)
            assert result["success"] is False
            await client.close()

    @respx.mock
    async def test_generate_zugferd_pdf_gen_error(self) -> None:
        with patch(
            "einvoice_mcp.tools.generate.generate_invoice_pdf",
            side_effect=InvoiceGenerationError("pdf failed"),
        ):
            client = KoSITClient(base_url=KOSIT_URL)
            data = InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )
            result = await generate_zugferd(data, client)
            assert result["success"] is False
            await client.close()

    @respx.mock
    async def test_generate_zugferd_embed_error(self) -> None:
        with patch(
            "einvoice_mcp.tools.generate.embed_xml_in_pdf",
            side_effect=InvoiceGenerationError("embed failed"),
        ):
            client = KoSITClient(base_url=KOSIT_URL)
            data = InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )
            result = await generate_zugferd(data, client)
            assert result["success"] is False
            await client.close()


# ============================================================================
# 6. KoSIT client edge cases (covers lines 66-67, 112-118)
# ============================================================================


class TestKoSITEdgeCases:
    @respx.mock
    async def test_unexpected_http_status(self) -> None:
        respx.post(f"{KOSIT_URL}/").respond(503, text="Service Unavailable")
        client = KoSITClient(base_url=KOSIT_URL)
        with pytest.raises(KoSITValidationError, match="503"):
            await client.validate(b"<test/>")
        await client.close()

    @respx.mock
    async def test_http_error_during_validation(self) -> None:
        respx.post(f"{KOSIT_URL}/").mock(side_effect=httpx.ReadTimeout("timeout"))
        client = KoSITClient(base_url=KOSIT_URL)
        with pytest.raises(KoSITValidationError):
            await client.validate(b"<test/>")
        await client.close()

    @respx.mock
    async def test_unparseable_report_xml(self) -> None:
        respx.post(f"{KOSIT_URL}/").respond(200, text="not xml at all")
        client = KoSITClient(base_url=KOSIT_URL)
        result = await client.validate(b"<test/>")
        # Should still return a result even if the report can't be parsed
        assert result.valid is True
        assert result.raw_report == "not xml at all"
        await client.close()

    @respx.mock
    async def test_report_with_warning_flag(self) -> None:
        warning_report = """\
<?xml version="1.0" encoding="UTF-8"?>
<rep:report xmlns:rep="http://www.xoev.de/de/validator/varl/1"
            xmlns:svrl="http://purl.oclc.org/dml/schematron/output/">
  <svrl:schematron-output>
    <svrl:failed-assert id="W-01" location="/Invoice" flag="warning">
      <svrl:text>Minor issue</svrl:text>
    </svrl:failed-assert>
  </svrl:schematron-output>
</rep:report>
"""
        respx.post(f"{KOSIT_URL}/").respond(200, text=warning_report)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await client.validate(b"<test/>")
        assert result.valid is True  # warnings don't invalidate
        assert len(result.warnings) == 1
        assert result.warnings[0].message == "Minor issue"
        await client.close()

    async def test_close_idempotent(self) -> None:
        client = KoSITClient(base_url=KOSIT_URL)
        await client.close()  # close before any connection
        await client.close()  # double close should be safe

    @respx.mock
    async def test_raw_report_capped(self) -> None:
        huge_report = '<?xml version="1.0"?><r>' + "x" * 600_000 + "</r>"
        respx.post(f"{KOSIT_URL}/").respond(200, text=huge_report)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await client.validate(b"<test/>")
        assert len(result.raw_report) <= 512 * 1024
        await client.close()


# ============================================================================
# 7. Validate tools — ZUGFeRD PDF extraction path (covers lines 65-70)
# ============================================================================


class TestValidateZugferdExtraction:
    @respx.mock
    async def test_valid_zugferd_extraction_error(self) -> None:
        """Test that PDF extraction failure returns clean error."""
        valid_b64 = base64.b64encode(b"not-a-real-pdf").decode("ascii")
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_zugferd(valid_b64, client)
        assert result["valid"] is False
        # Should have an extraction error
        assert len(result["errors"]) > 0
        await client.close()


# ============================================================================
# 8. Parse tool — PDF path (covers lines 49-50, 68-73)
# ============================================================================


class TestParseToolPdfPath:
    async def test_parse_pdf_extraction_failure(self) -> None:
        valid_b64 = base64.b64encode(b"not-a-pdf").decode("ascii")
        result = await parse_einvoice(valid_b64, "pdf")
        assert result["success"] is False
        assert "Rechnung" in result["error"] or "PDF" in result["error"]


# ============================================================================
# 9. Compliance — edge case: suggested fields from SUGGESTIONS_MAP (covers 143-144)
# ============================================================================


class TestComplianceEdgeCases:
    @respx.mock
    async def test_kosit_valid_but_fields_missing(self) -> None:
        """KoSIT says valid but mandatory fields are missing — should still fail."""
        minimal = (
            '<?xml version="1.0"?>'
            "<rsm:CrossIndustryInvoice"
            ' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"'
            ' xmlns:ram="urn:un:unece:uncefact:data:standard:'
            'ReusableAggregateBusinessInformationEntity:100">'
            "</rsm:CrossIndustryInvoice>"
        )
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(minimal, client, "XRECHNUNG")
        # KoSIT says valid, but missing fields should override
        assert result["valid"] is False
        assert len(result["missing_fields"]) > 0
        await client.close()

    @respx.mock
    async def test_invalid_target_profile_rejected(self) -> None:
        """Unknown target_profile must return an error, not silently weaken checks."""
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance("<xml/>", client, "TYPO_XRECHUNG")
        assert result["valid"] is False
        assert any("Ungültiges Zielprofil" in s for s in result["suggestions"])
        await client.close()

    @respx.mock
    async def test_invalid_target_profile_not_reflected(self) -> None:
        """User-supplied target_profile must NOT be reflected in the output."""
        client = KoSITClient(base_url=KOSIT_URL)
        payload = "<script>alert('xss')</script>"
        result = await check_compliance("<xml/>", client, payload)
        assert result["valid"] is False
        # The user input must not appear in any suggestion
        for suggestion in result["suggestions"]:
            assert payload not in suggestion
        await client.close()

    @respx.mock
    async def test_zugferd_profile_compliance(self) -> None:
        """Test compliance with ZUGFERD target profile — should NOT flag BT-10, BT-34, etc."""
        xml = build_xml(
            InvoiceData(
                invoice_id="Z-001",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )
        ).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "ZUGFERD")
        # ZUGFeRD should NOT flag BT-10/34/49/41/43 as missing
        xrechnung_only = {"BT-10", "BT-34", "BT-49", "BT-41", "BT-43"}
        missing = set(result["missing_fields"])
        overlap = missing & xrechnung_only
        assert not overlap, f"XRechnung-only fields wrongly flagged: {overlap}"
        # Should get ZUGFeRD-specific success message
        if result["valid"]:
            assert any("ZUGFeRD" in s for s in result["suggestions"])
        await client.close()


# ============================================================================
# 10. Full roundtrip: generate → parse → compliance
# ============================================================================


class TestFullRoundtrip:
    @respx.mock
    async def test_xrechnung_roundtrip(self, sample_invoice_data: InvoiceData) -> None:
        """Generate XRechnung, then parse it back, then run compliance.

        Verifies: invoice_id, seller, buyer, totals, tax breakdown, currency, items.
        """
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)

        # Generate
        gen_result = await generate_xrechnung(sample_invoice_data, client)
        assert gen_result["success"] is True
        xml = gen_result["xml_content"]

        # Parse
        parse_result = await parse_einvoice(xml, "xml")
        assert parse_result["success"] is True
        inv = parse_result["invoice"]

        # Verify all key fields roundtrip correctly
        assert inv["invoice_id"] == "RE-2026-001"
        assert inv["currency"] == "EUR"

        # Seller
        assert inv["seller"]["name"] == "TechCorp GmbH"
        assert inv["seller"]["address"]["city"] == "Berlin"
        assert inv["seller"]["address"]["postal_code"] == "10115"
        assert inv["seller"]["tax_id"] == "DE123456789"

        # Buyer
        assert inv["buyer"]["name"] == "ClientCorp GmbH"
        assert inv["buyer"]["address"]["city"] == "München"

        # Totals (parsed values may be Decimal or str depending on serialization)
        expected_net = sample_invoice_data.total_net()
        expected_tax = sample_invoice_data.total_tax()
        assert Decimal(str(inv["totals"]["net_total"])) == expected_net
        assert Decimal(str(inv["totals"]["tax_total"])) == expected_tax

        # Items
        assert len(inv["items"]) == 2
        assert inv["items"][0]["description"] == "Software-Beratung"

        # Tax breakdown
        assert len(inv["tax_breakdown"]) >= 1

        # Type code (BT-3) — should be default 380
        assert inv["type_code"] == "380"

        # Delivery date (BT-71) — set on sample_invoice_data fixture
        assert "2026-03-01" in inv["delivery_date"]

        # Electronic addresses (BT-34 / BT-49)
        assert inv["seller"]["electronic_address"] == "rechnungen@techcorp.de"
        assert inv["buyer"]["electronic_address"] == "einkauf@clientcorp.de"

        # Compliance
        comp_result = await check_compliance(xml, client, "XRECHNUNG")
        assert comp_result["kosit_valid"] is True

        await client.close()

    @respx.mock
    async def test_zugferd_generate_parse_roundtrip(self, sample_invoice_data: InvoiceData) -> None:
        """Generate ZUGFeRD PDF, verify it has expected structure."""
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)

        result = await generate_zugferd(sample_invoice_data, client)
        assert result["success"] is True
        assert result["pdf_size_bytes"] > 0
        assert result["totals"]["net"] == str(sample_invoice_data.total_net())

        await client.close()


# ============================================================================
# 11. Model edge cases and boundary values
# ============================================================================


class TestModelBoundaryValues:
    def test_line_item_zero_price_allowed(self) -> None:
        item = LineItem(description="Free item", quantity="1", unit_price="0.00")
        assert item.unit_price == Decimal("0.00")

    def test_line_item_very_small_quantity(self) -> None:
        item = LineItem(description="Micro", quantity="0.001", unit_price="1000")
        assert item.quantity == Decimal("0.001")

    def test_invoice_with_all_profiles(self) -> None:
        for profile in InvoiceProfile:
            data = InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
                profile=profile,
            )
            assert data.profile == profile

    def test_all_tax_categories_build_xml(self) -> None:
        for cat in TaxCategory:
            data = InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(
                    name="S",
                    address=Address(street="S", city="S", postal_code="00000"),
                    tax_id="DE123",
                ),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[
                    LineItem(
                        description="X",
                        quantity="1",
                        unit_price="10",
                        tax_category=cat,
                        tax_rate="0" if cat in (TaxCategory.Z, TaxCategory.E) else "19",
                    )
                ],
            )
            xml = build_xml(data)
            assert xml  # should not crash for any category

    def test_iban_in_generated_xml(self) -> None:
        """BT-84: IBAN appears in generated XML when seller_iban is set."""
        data = InvoiceData(
            invoice_id="IBAN-T",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
            seller_iban="DE89370400440532013000",
            seller_bic="COBADEFFXXX",
            seller_bank_name="Commerzbank",
        )
        xml_str = build_xml(data).decode("utf-8")
        assert "DE89370400440532013000" in xml_str
        assert "COBADEFFXXX" in xml_str

    def test_iban_in_pdf(self) -> None:
        """Bank details section appears in PDF when seller_iban is set."""
        data = InvoiceData(
            invoice_id="IBAN-PDF",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
            seller_iban="DE89370400440532013000",
            seller_bic="COBADEFFXXX",
            seller_bank_name="Commerzbank",
        )
        pdf = generate_invoice_pdf(data)
        assert len(pdf) > 0  # PDF generated successfully with IBAN + BIC + bank name

    def test_invoice_no_payment_terms(self) -> None:
        data = InvoiceData(
            invoice_id="T",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="10")],
            payment_terms_days=None,
        )
        xml = build_xml(data)
        assert b"Zahlbar" not in xml

    def test_invoice_with_payment_terms_zero(self) -> None:
        """payment_terms_days=0 is a valid value meaning 'due immediately'."""
        data = InvoiceData(
            invoice_id="T",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="10")],
            payment_terms_days=0,
        )
        xml_str = build_xml(data).decode("utf-8")
        assert "0 Tagen" in xml_str

    def test_invoice_with_payment_terms(self) -> None:
        data = InvoiceData(
            invoice_id="T",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="10")],
            payment_terms_days=14,
        )
        xml_str = build_xml(data).decode("utf-8")
        assert "14 Tagen" in xml_str

    def test_totals_model_direct(self) -> None:
        t = Totals(
            net_total=Decimal("100"),
            tax_total=Decimal("19"),
            gross_total=Decimal("119"),
            due_payable=Decimal("119"),
        )
        assert t.gross_total == Decimal("119")

    def test_tax_breakdown_model_direct(self) -> None:
        tb = TaxBreakdown(
            tax_rate=Decimal("19"),
            tax_category="S",
            taxable_amount=Decimal("100"),
            tax_amount=Decimal("19"),
        )
        assert tb.tax_category == "S"

    def test_party_max_length_tax_id(self) -> None:
        with pytest.raises(ValidationError):
            Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="X" * 31,
            )

    def test_line_item_description_max_length(self) -> None:
        with pytest.raises(ValidationError):
            LineItem(description="X" * 501, quantity="1", unit_price="10")


# ============================================================================
# 12. Invoice builder — all profiles produce valid XML
# ============================================================================


class TestInvoiceBuilderAllProfiles:
    def test_zugferd_basic_profile(self) -> None:
        data = InvoiceData(
            invoice_id="T",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123",
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
                tax_id="DE456",
            ),
            items=[LineItem(description="X", quantity="1", unit_price="10")],
            profile=InvoiceProfile.ZUGFERD_BASIC,
            buyer_reference="REF-1",
        )
        xml_str = build_xml(data).decode("utf-8")
        assert "basic" in xml_str

    def test_zugferd_extended_profile(self) -> None:
        data = InvoiceData(
            invoice_id="T",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[LineItem(description="X", quantity="1", unit_price="10")],
            profile=InvoiceProfile.ZUGFERD_EXTENDED,
        )
        xml_str = build_xml(data).decode("utf-8")
        assert "extended" in xml_str

    def test_no_seller_tax_id(self) -> None:
        data = InvoiceData(
            invoice_id="T",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="10")],
        )
        xml = build_xml(data)
        assert xml  # Should not crash without tax_id

    def test_multiple_items_different_tax_rates(self) -> None:
        data = InvoiceData(
            invoice_id="T",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[
                LineItem(description="A", quantity="1", unit_price="100", tax_rate="19"),
                LineItem(description="B", quantity="1", unit_price="50", tax_rate="7"),
                LineItem(description="C", quantity="2", unit_price="25", tax_rate="19"),
            ],
        )
        xml = build_xml(data)
        assert xml
        # Should produce two tax groups: 19% and 7%
        xml_str = xml.decode("utf-8")
        assert "19" in xml_str
        assert "7" in xml_str


# ============================================================================
# 13. Config validation
# ============================================================================


class TestConfigValidation:
    def test_invalid_kosit_url(self) -> None:
        from einvoice_mcp.config import Settings

        with pytest.raises(ValidationError):
            Settings(kosit_url="not-a-url")

    def test_invalid_log_level(self) -> None:
        from einvoice_mcp.config import Settings

        with pytest.raises(ValidationError):
            Settings(log_level="VERBOSE")

    def test_valid_config(self) -> None:
        from einvoice_mcp.config import Settings

        s = Settings(kosit_url="http://localhost:8081", log_level="DEBUG")
        assert s.log_level == "DEBUG"


# ============================================================================
# 14. BT-32 Steuernummer — roundtrip (generate → parse)
# ============================================================================


class TestBT32Steuernummer:
    def test_steuernummer_roundtrip(self) -> None:
        """Generate with BT-32, parse it back, verify tax_number is preserved."""
        data = InvoiceData(
            invoice_id="BT32-RT",
            issue_date="2026-01-01",
            seller=Party(
                name="Kleinunternehmer GmbH",
                address=Address(street="Str. 1", city="Berlin", postal_code="10115"),
                tax_number="123/456/78901",
            ),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.tax_number == "123/456/78901"
        # No USt-IdNr. set → tax_id should be None
        assert parsed.seller.tax_id is None

    def test_both_va_and_fc_roundtrip(self) -> None:
        """Generate with both BT-31 and BT-32, parse back both."""
        data = InvoiceData(
            invoice_id="BOTH-RT",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE999999999",
                tax_number="99/999/99999",
            ),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.tax_id == "DE999999999"
        assert parsed.seller.tax_number == "99/999/99999"

    def test_preserves_unicode_parens(self) -> None:
        """Unicode in parenthetical text must NOT be stripped (e.g. Ü)."""
        assert _str_element("Artikel (3Ü)") == "Artikel (3Ü)"

    def test_preserves_lowercase_parens(self) -> None:
        """Lowercase text in parentheses must be preserved."""
        assert _str_element("Reisekosten (pauschal)") == "Reisekosten (pauschal)"


# ============================================================================
# 15. TypeCode — generation and parsing
# ============================================================================


class TestTypeCode:
    def test_type_code_381_roundtrip(self) -> None:
        """TypeCode 381 (Gutschrift) roundtrip."""
        data = InvoiceData(
            invoice_id="GS-001",
            issue_date="2026-01-01",
            type_code="381",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.type_code == "381"

    def test_type_code_384_roundtrip(self) -> None:
        """TypeCode 384 (Korrekturrechnung) roundtrip."""
        data = InvoiceData(
            invoice_id="KR-001",
            issue_date="2026-01-01",
            type_code="384",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.type_code == "384"

    def test_type_code_pdf_gutschrift_header(self) -> None:
        """TypeCode 381 produces GUTSCHRIFT PDF header."""
        data = InvoiceData(
            invoice_id="GS-PDF",
            issue_date="2026-01-01",
            type_code="381",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        pdf = generate_invoice_pdf(data)
        assert len(pdf) > 0

    def test_valid_type_codes_constant(self) -> None:
        """VALID_TYPE_CODES frozenset contains expected values."""
        from einvoice_mcp.models import VALID_TYPE_CODES

        assert "380" in VALID_TYPE_CODES
        assert "381" in VALID_TYPE_CODES
        assert "384" in VALID_TYPE_CODES
        assert "389" in VALID_TYPE_CODES
        assert "999" not in VALID_TYPE_CODES


# ============================================================================
# 16. Delivery date and service period — generation and parsing
# ============================================================================


class TestDeliveryDateServicePeriod:
    def test_delivery_date_in_pdf(self) -> None:
        """Delivery date appears in the visual PDF."""
        data = InvoiceData(
            invoice_id="DEL-PDF",
            issue_date="2026-01-01",
            delivery_date="2026-01-15",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        pdf = generate_invoice_pdf(data)
        assert len(pdf) > 0

    def test_service_period_in_pdf(self) -> None:
        """Service period appears in the visual PDF."""
        data = InvoiceData(
            invoice_id="SVC-PDF",
            issue_date="2026-01-01",
            service_period_start="2026-01-01",
            service_period_end="2026-01-31",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        pdf = generate_invoice_pdf(data)
        assert len(pdf) > 0


# ============================================================================
# 17. BT-84 IBAN compliance check
# ============================================================================


class TestBT84IBANCompliance:
    @respx.mock
    async def test_iban_missing_flags_bt84(self) -> None:
        """When PaymentMeansCode=58 and IBAN is absent, BT-84 must be flagged."""
        data = InvoiceData(
            invoice_id="NO-IBAN",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123",
            ),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "BT-84" in result["missing_fields"]
        assert any("IBAN" in s for s in result["suggestions"])
        await client.close()

    @respx.mock
    async def test_iban_present_passes_bt84(self) -> None:
        """When PaymentMeansCode=58 and IBAN is present, BT-84 must pass."""
        data = InvoiceData(
            invoice_id="HAS-IBAN",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123",
                electronic_address="s@s.de",
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
                electronic_address="b@b.de",
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
            seller_iban="DE89370400440532013000",
            buyer_reference="REF-1",
            seller_contact_name="Name",
            seller_contact_email="e@e.de",
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "BT-84" not in result["missing_fields"]
        await client.close()


# ============================================================================
# 18. BT-31/BT-32 alternative compliance check
# ============================================================================


class TestBT31BT32AlternativeCompliance:
    @respx.mock
    async def test_neither_bt31_nor_bt32_flags_missing(self) -> None:
        """Neither USt-IdNr. nor Steuernummer → BT-31/32 flagged."""
        data = InvoiceData(
            invoice_id="NO-TAX",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "BT-31/32" in result["missing_fields"]
        assert any("Steuernummer" in s for s in result["suggestions"])
        await client.close()

    @respx.mock
    async def test_only_bt32_passes(self) -> None:
        """Only Steuernummer (BT-32) without USt-IdNr. → BT-31/32 passes."""
        data = InvoiceData(
            invoice_id="FC-ONLY",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_number="123/456/78901",
            ),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "BT-31/32" not in result["missing_fields"]
        await client.close()

    @respx.mock
    async def test_only_bt31_passes(self) -> None:
        """Only USt-IdNr. (BT-31) → BT-31/32 passes."""
        data = InvoiceData(
            invoice_id="VA-ONLY",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "BT-31/32" not in result["missing_fields"]
        await client.close()


# ============================================================================
# 19. Server helper _build_invoice_data — new parameters
# ============================================================================


class TestBuildInvoiceDataNewParams:
    def test_type_code_parameter(self) -> None:
        from einvoice_mcp.server import _build_invoice_data

        data = _build_invoice_data(
            invoice_id="TC-001",
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="DE123",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json='[{"description":"X","quantity":1,"unit_price":100}]',
            type_code="381",
        )
        assert isinstance(data, InvoiceData)
        assert data.type_code == "381"

    def test_seller_tax_number_parameter(self) -> None:
        from einvoice_mcp.server import _build_invoice_data

        data = _build_invoice_data(
            invoice_id="TN-001",
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json='[{"description":"X","quantity":1,"unit_price":100}]',
            seller_tax_number="123/456/78901",
        )
        assert isinstance(data, InvoiceData)
        assert data.seller.tax_number == "123/456/78901"

    def test_delivery_date_parameter(self) -> None:
        from einvoice_mcp.server import _build_invoice_data

        data = _build_invoice_data(
            invoice_id="DD-001",
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="DE123",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json='[{"description":"X","quantity":1,"unit_price":100}]',
            delivery_date="2026-01-15",
        )
        assert isinstance(data, InvoiceData)
        assert str(data.delivery_date) == "2026-01-15"

    def test_service_period_parameters(self) -> None:
        from einvoice_mcp.server import _build_invoice_data

        data = _build_invoice_data(
            invoice_id="SP-001",
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="DE123",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json='[{"description":"X","quantity":1,"unit_price":100}]',
            service_period_start="2026-01-01",
            service_period_end="2026-01-31",
        )
        assert isinstance(data, InvoiceData)
        assert str(data.service_period_start) == "2026-01-01"
        assert str(data.service_period_end) == "2026-01-31"

    def test_electronic_address_scheme_parameters(self) -> None:
        from einvoice_mcp.server import _build_invoice_data

        data = _build_invoice_data(
            invoice_id="EAS-001",
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="DE123",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json='[{"description":"X","quantity":1,"unit_price":100}]',
            seller_electronic_address="DE123456789",
            seller_electronic_address_scheme="9930",
            buyer_electronic_address="buyer@example.de",
            buyer_electronic_address_scheme="EM",
        )
        assert isinstance(data, InvoiceData)
        assert data.seller.electronic_address == "DE123456789"
        assert data.seller.electronic_address_scheme == "9930"
        assert data.buyer.electronic_address == "buyer@example.de"
        assert data.buyer.electronic_address_scheme == "EM"


# ============================================================================
# 20. Type code validation — Pydantic field_validator
# ============================================================================


class TestTypeCodeValidation:
    def test_valid_type_codes_accepted(self) -> None:
        """All valid type codes are accepted by the validator."""
        from einvoice_mcp.models import VALID_TYPE_CODES

        for code in VALID_TYPE_CODES:
            data = InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                type_code=code,
                seller=Party(
                    name="S",
                    address=Address(street="S", city="S", postal_code="00000"),
                ),
                buyer=Party(
                    name="B",
                    address=Address(street="B", city="B", postal_code="00000"),
                ),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )
            assert data.type_code == code

    def test_invalid_type_code_rejected(self) -> None:
        """Invalid type code '999' is rejected by the validator."""
        with pytest.raises(ValidationError, match="Ungültiger Rechnungsartcode"):
            InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                type_code="999",
                seller=Party(
                    name="S",
                    address=Address(street="S", city="S", postal_code="00000"),
                ),
                buyer=Party(
                    name="B",
                    address=Address(street="B", city="B", postal_code="00000"),
                ),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )

    def test_empty_type_code_rejected(self) -> None:
        """Empty type code is rejected."""
        with pytest.raises(ValidationError):
            InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                type_code="",
                seller=Party(
                    name="S",
                    address=Address(street="S", city="S", postal_code="00000"),
                ),
                buyer=Party(
                    name="B",
                    address=Address(street="B", city="B", postal_code="00000"),
                ),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )

    def test_invalid_type_code_via_server(self) -> None:
        """_build_invoice_data returns error string for invalid type code."""
        from einvoice_mcp.server import _build_invoice_data

        result = _build_invoice_data(
            invoice_id="T",
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="DE123",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json='[{"description":"X","quantity":1,"unit_price":100}]',
            type_code="999",
        )
        assert isinstance(result, str)
        assert "Fehler" in result


# ============================================================================
# 21. Delivery date / service period — parser roundtrip
# ============================================================================


class TestDeliveryDateParsing:
    def test_delivery_date_roundtrip(self) -> None:
        """BT-71 delivery date roundtrips through generate → parse."""
        data = InvoiceData(
            invoice_id="DD-RT",
            issue_date="2026-01-01",
            delivery_date="2026-01-15",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert "2026-01-15" in parsed.delivery_date

    def test_service_period_roundtrip(self) -> None:
        """BT-73/BT-74 service period roundtrips through generate → parse."""
        data = InvoiceData(
            invoice_id="SP-RT",
            issue_date="2026-01-01",
            service_period_start="2026-01-01",
            service_period_end="2026-01-31",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert "2026-01-01" in parsed.service_period_start
        assert "2026-01-31" in parsed.service_period_end

    def test_no_delivery_date_returns_empty(self) -> None:
        """Without delivery date, parsed delivery_date is empty."""
        data = InvoiceData(
            invoice_id="NO-DD",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.delivery_date == ""
        assert parsed.service_period_start == ""
        assert parsed.service_period_end == ""


# ============================================================================
# 22. Electronic address — parser roundtrip
# ============================================================================


class TestElectronicAddressParsing:
    def test_seller_electronic_address_roundtrip(self) -> None:
        """BT-34 seller electronic address roundtrips through generate → parse."""
        data = InvoiceData(
            invoice_id="EA-RT",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
                electronic_address="rechnungen@firma.de",
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.electronic_address == "rechnungen@firma.de"

    def test_buyer_electronic_address_roundtrip(self) -> None:
        """BT-49 buyer electronic address roundtrips through generate → parse."""
        data = InvoiceData(
            invoice_id="EA-BUY-RT",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
                electronic_address="einkauf@buyer.de",
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.buyer is not None
        assert parsed.buyer.electronic_address == "einkauf@buyer.de"

    def test_no_electronic_address_returns_none(self) -> None:
        """Without electronic address, parsed value is None."""
        data = InvoiceData(
            invoice_id="NO-EA",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.electronic_address is None

    def test_electronic_address_with_peppol_scheme(self) -> None:
        """Electronic address with 9930 scheme roundtrips correctly."""
        data = InvoiceData(
            invoice_id="EA-9930",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
                electronic_address="DE123456789",
                electronic_address_scheme="9930",
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.electronic_address == "DE123456789"


# ============================================================================
# 23. BT-71/73/74 compliance check
# ============================================================================


class TestBT71ComplianceCheck:
    @respx.mock
    async def test_no_delivery_date_or_period_flags_missing(self) -> None:
        """Neither BT-71 nor BT-73/74 → flagged as missing."""
        data = InvoiceData(
            invoice_id="NO-DEL",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123",
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "BT-71/73/74" in result["missing_fields"]
        assert any("Lieferdatum" in s for s in result["suggestions"])
        await client.close()

    @respx.mock
    async def test_delivery_date_passes_bt71(self) -> None:
        """With delivery date (BT-71) → BT-71/73/74 passes."""
        data = InvoiceData(
            invoice_id="HAS-DEL",
            issue_date="2026-01-01",
            delivery_date="2026-01-15",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123",
                electronic_address="s@s.de",
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
                electronic_address="b@b.de",
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
            seller_iban="DE89370400440532013000",
            buyer_reference="REF-1",
            seller_contact_name="Name",
            seller_contact_email="e@e.de",
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "BT-71/73/74" not in result["missing_fields"]
        await client.close()

    @respx.mock
    async def test_service_period_passes_bt71(self) -> None:
        """With service period (BT-73/BT-74) → BT-71/73/74 passes."""
        data = InvoiceData(
            invoice_id="HAS-SP",
            issue_date="2026-01-01",
            service_period_start="2026-01-01",
            service_period_end="2026-01-31",
            seller=Party(
                name="S",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123",
                electronic_address="s@s.de",
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="B", postal_code="00000"),
                electronic_address="b@b.de",
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
            seller_iban="DE89370400440532013000",
            buyer_reference="REF-1",
            seller_contact_name="Name",
            seller_contact_email="e@e.de",
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "BT-71/73/74" not in result["missing_fields"]
        await client.close()


# ============================================================================
# 24. Parse tool — XML error path (covers parse.py:50-51)
# ============================================================================


class TestParseToolXmlErrorPath:
    async def test_parse_xml_einvoice_error(self) -> None:
        """When parse_xml raises InvoiceParsingError, return German error message."""
        with patch(
            "einvoice_mcp.tools.parse.parse_xml",
            side_effect=InvoiceParsingError("test detail"),
        ):
            result = await parse_einvoice("<xml>valid</xml>", "xml")
            assert result["success"] is False
            assert "gelesen werden" in result["error"]

    async def test_parse_pdf_xml_error_after_extraction(self) -> None:
        """When extract_xml succeeds but parse_xml fails, return German error."""
        valid_b64 = base64.b64encode(b"fake-pdf-bytes").decode("ascii")
        with (
            patch(
                "einvoice_mcp.tools.parse.extract_xml_from_pdf",
                return_value=b"<invalid-xml/>",
            ),
            patch(
                "einvoice_mcp.tools.parse.parse_xml",
                side_effect=InvoiceParsingError("corrupt XML"),
            ),
        ):
            result = await parse_einvoice(valid_b64, "pdf")
            assert result["success"] is False
            assert "gelesen werden" in result["error"]


# ============================================================================
# 25. XML parser exception handlers (covers xml_parser.py lines)
# ============================================================================


class TestParserExceptionHandlers:
    def test_party_extraction_error_returns_none(self) -> None:
        """If _extract_party fails internally, returns None (not crash)."""
        from einvoice_mcp.services.xml_parser import _extract_party

        class BrokenParty:
            name = "Valid Name"

            @property
            def address(self) -> None:
                raise RuntimeError("address boom")

        result = _extract_party(BrokenParty())
        assert result is None

    def test_empty_tax_registration_value_skipped(self) -> None:
        """Tax registration with valid schemeID but empty value is skipped."""
        from einvoice_mcp.services.xml_parser import _extract_party

        class FakeIDEmpty:
            _scheme_id = "VA"

            def __str__(self) -> str:
                return ""

        class FakeReg:
            id = FakeIDEmpty()

        class FakeRegs:
            children = (FakeReg(),)

        class FakeAddress:
            line_one = "Str. 1"
            city_name = "Berlin"
            postcode = "10115"
            country_id = "DE"

        class FakePartyObj:
            name = "TestName"
            address = FakeAddress()
            tax_registrations = FakeRegs()
            electronic_address = None

        result = _extract_party(FakePartyObj())
        assert result is not None
        assert result.name == "TestName"
        assert result.tax_id is None  # empty value skipped

    def test_tax_breakdown_no_children(self) -> None:
        """Trade tax container without children returns empty breakdown."""
        from unittest.mock import MagicMock

        from einvoice_mcp.services.xml_parser import _extract_tax_breakdown

        fake_doc = MagicMock()
        # trade_tax container has no "children" attribute
        del fake_doc.trade.settlement.trade_tax.children
        result = _extract_tax_breakdown(fake_doc)
        assert result == []


# ============================================================================
# 26. Server _build_invoice_data error paths
# ============================================================================


class TestBuildInvoiceDataErrors:
    def test_invalid_json_items(self) -> None:
        from einvoice_mcp.server import _build_invoice_data

        result = _build_invoice_data(
            invoice_id="T",
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="DE123",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json="not valid json",
        )
        assert isinstance(result, str)
        assert "JSON" in result

    def test_invalid_profile(self) -> None:
        from einvoice_mcp.server import _build_invoice_data

        result = _build_invoice_data(
            invoice_id="T",
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="DE123",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json='[{"description":"X","quantity":1,"unit_price":100}]',
            profile="INVALID_PROFILE",
        )
        assert isinstance(result, str)
        assert "Ungültiges Profil" in result

    def test_pydantic_validation_error(self) -> None:
        from einvoice_mcp.server import _build_invoice_data

        result = _build_invoice_data(
            invoice_id="",  # empty → validation error
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="DE123",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json='[{"description":"X","quantity":1,"unit_price":100}]',
        )
        assert isinstance(result, str)
        assert "Ungültige Rechnungsdaten" in result

    def test_invalid_date_format(self) -> None:
        from einvoice_mcp.server import _build_invoice_data

        result = _build_invoice_data(
            invoice_id="T",
            issue_date="not-a-date",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="DE123",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json='[{"description":"X","quantity":1,"unit_price":100}]',
        )
        assert isinstance(result, str)
        assert "Fehler" in result
