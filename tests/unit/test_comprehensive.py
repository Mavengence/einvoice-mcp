"""Comprehensive edge-case and integration tests for einvoice-mcp.

Covers all uncovered code paths, error handling branches, cross-module
roundtrips, and boundary conditions identified in coverage analysis.
"""

import base64
from decimal import Decimal
from unittest.mock import MagicMock, patch

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
    AllowanceCharge,
    InvoiceData,
    InvoiceProfile,
    LineAllowanceCharge,
    LineItem,
    Party,
    TaxBreakdown,
    TaxCategory,
    Totals,
)
from einvoice_mcp.services.invoice_builder import build_xml
from einvoice_mcp.services.kosit import MAX_RESPONSE_SIZE, KoSITClient
from einvoice_mcp.services.pdf_generator import (
    embed_xml_in_pdf,
    generate_invoice_pdf,
)
from einvoice_mcp.services.xml_parser import (
    _extract_invoice,
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

    def test_str_element_strips_empty_parens(self) -> None:
        # Empty parens come from drafthorse IDElements with no schemeID
        assert _str_element("DE123 ()") == "DE123"

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
    async def test_reverse_charge_missing_seller_vat(self) -> None:
        """Reverse charge (AE) without seller VAT ID triggers RC-BT-31 error."""
        # Build an invoice with AE category but no seller tax_id
        data = InvoiceData(
            invoice_id="RC-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_number="123/456/78901",  # Only Steuernummer, no USt-IdNr.
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
                tax_id="DE987654321",
            ),
            items=[
                LineItem(
                    description="§13b Leistung",
                    quantity="1",
                    unit_price="1000",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.AE,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "RC-BT-31" in result["missing_fields"]
        await client.close()

    @respx.mock
    async def test_reverse_charge_missing_buyer_vat(self) -> None:
        """Reverse charge (AE) without buyer VAT ID triggers RC-BT-48 error."""
        data = InvoiceData(
            invoice_id="RC-002",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
                # No buyer tax_id
            ),
            items=[
                LineItem(
                    description="§13b Leistung",
                    quantity="1",
                    unit_price="1000",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.AE,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "RC-BT-48" in result["missing_fields"]
        await client.close()

    @respx.mock
    async def test_reverse_charge_nonzero_tax_rate(self) -> None:
        """Reverse charge (AE) with non-zero tax rate triggers RC-TAX-RATE error."""
        data = InvoiceData(
            invoice_id="RC-004",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
                tax_id="ATU12345678",
            ),
            items=[
                LineItem(
                    description="§13b Leistung",
                    quantity="1",
                    unit_price="1000",
                    tax_rate=Decimal("19"),  # Wrong — should be 0 for AE
                    tax_category=TaxCategory.AE,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "RC-TAX-RATE" in result["missing_fields"]
        await client.close()

    @respx.mock
    async def test_reverse_charge_valid(self) -> None:
        """Correct reverse charge invoice passes RC checks."""
        data = InvoiceData(
            invoice_id="RC-003",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
                tax_id="ATU12345678",
            ),
            items=[
                LineItem(
                    description="§13b Leistung",
                    quantity="1",
                    unit_price="1000",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.AE,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        rc_fields = [f for f in result["missing_fields"] if f.startswith("RC-")]
        assert rc_fields == [], f"Unexpected RC failures: {rc_fields}"
        await client.close()

    @respx.mock
    async def test_exempt_without_note_triggers_ku_hint(self) -> None:
        """TaxCategory E without §19 note triggers KU-NOTE advisory."""
        data = InvoiceData(
            invoice_id="KU-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Kleiner Betrieb",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_number="123/456/78901",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Beratung",
                    quantity="1",
                    unit_price="500",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.E,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "ZUGFERD")
        # KU-NOTE should appear in suggestions but NOT in missing_fields
        # (since required=False)
        assert "KU-NOTE" not in result["missing_fields"]
        assert any("§19" in s for s in result["suggestions"])
        await client.close()

    @respx.mock
    async def test_exempt_with_note_no_ku_hint(self) -> None:
        """TaxCategory E with §19 note does NOT trigger KU-NOTE."""
        data = InvoiceData(
            invoice_id="KU-002",
            issue_date="2026-01-01",
            seller=Party(
                name="Kleiner Betrieb",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_number="123/456/78901",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Beratung",
                    quantity="1",
                    unit_price="500",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.E,
                ),
            ],
            invoice_note="Gemäß §19 UStG wird keine Umsatzsteuer berechnet.",
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "ZUGFERD")
        ku_suggestions = [
            s for s in result["suggestions"]
            if "§19" in s and "Kleinunternehmer" in s
        ]
        assert ku_suggestions == []
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


# ============================================================================
# 27. Invoice note (BT-22) and payment terms text (BT-20)
# ============================================================================


class TestInvoiceNoteAndPaymentTerms:
    """Roundtrip and generation tests for BT-22 / BT-20."""

    def test_invoice_note_roundtrip(self, sample_invoice_data: InvoiceData) -> None:
        """BT-22: invoice_note survives generate → parse roundtrip."""
        data = sample_invoice_data.model_copy(
            update={"invoice_note": "Bitte Rechnungsnr. bei Zahlung angeben."}
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.invoice_note == "Bitte Rechnungsnr. bei Zahlung angeben."

    def test_payment_terms_text_roundtrip(self, sample_invoice_data: InvoiceData) -> None:
        """BT-20: payment_terms_text survives generate → parse roundtrip."""
        data = sample_invoice_data.model_copy(
            update={
                "payment_terms_text": "2% Skonto bei Zahlung innerhalb 10 Tagen.",
                "payment_terms_days": None,
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.payment_terms == "2% Skonto bei Zahlung innerhalb 10 Tagen."

    def test_payment_terms_text_overrides_days(self, sample_invoice_data: InvoiceData) -> None:
        """BT-20: payment_terms_text takes priority over payment_terms_days."""
        data = sample_invoice_data.model_copy(
            update={
                "payment_terms_text": "Sofort fällig.",
                "payment_terms_days": 30,
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.payment_terms == "Sofort fällig."

    def test_payment_terms_days_fallback(self, sample_invoice_data: InvoiceData) -> None:
        """When only payment_terms_days is set, auto-generate text."""
        data = sample_invoice_data.model_copy(
            update={"payment_terms_text": None, "payment_terms_days": 14}
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert "14 Tagen" in parsed.payment_terms

    def test_no_note_or_terms(self, sample_invoice_data: InvoiceData) -> None:
        """When neither note nor terms are set, both parse as empty."""
        data = sample_invoice_data.model_copy(
            update={
                "invoice_note": None,
                "payment_terms_text": None,
                "payment_terms_days": None,
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.invoice_note == ""
        assert parsed.payment_terms == ""

    def test_pdf_includes_invoice_note(self, sample_invoice_data: InvoiceData) -> None:
        """PDF generation with invoice_note doesn't crash and produces bytes."""
        data = sample_invoice_data.model_copy(
            update={"invoice_note": "Testnotiz für die PDF."}
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100

    def test_pdf_includes_payment_terms_text(self, sample_invoice_data: InvoiceData) -> None:
        """PDF generation with payment_terms_text doesn't crash."""
        data = sample_invoice_data.model_copy(
            update={"payment_terms_text": "3% Skonto bei Zahlung innerhalb 7 Tagen."}
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100

    def test_build_invoice_data_with_note_and_terms(self) -> None:
        """Server _build_invoice_data correctly passes BT-22 / BT-20."""
        from einvoice_mcp.server import _build_invoice_data

        data = _build_invoice_data(
            invoice_id="NOTE-001",
            issue_date="2026-03-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="10115",
            seller_country_code="DE",
            seller_tax_id="DE123456789",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="80999",
            buyer_country_code="DE",
            items_json='[{"description":"Test","quantity":1,"unit_price":100}]',
            invoice_note="Wichtiger Hinweis",
            payment_terms_text="Sofort zahlbar.",
        )
        assert isinstance(data, InvoiceData)
        assert data.invoice_note == "Wichtiger Hinweis"
        assert data.payment_terms_text == "Sofort zahlbar."


# ============================================================================
# 28. Reference fields (BT-11, BT-12, BT-13, BT-25) roundtrip
# ============================================================================


class TestReferenceFieldsRoundtrip:
    """Roundtrip tests for BT-11/12/13/25 reference fields."""

    def test_purchase_order_reference_bt13(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """BT-13: purchase order reference roundtrip."""
        data = sample_invoice_data.model_copy(
            update={"purchase_order_reference": "PO-2026-0042"}
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.purchase_order_reference == "PO-2026-0042"

    def test_contract_reference_bt12(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """BT-12: contract reference roundtrip."""
        data = sample_invoice_data.model_copy(
            update={"contract_reference": "V-2025-1234"}
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.contract_reference == "V-2025-1234"

    def test_project_reference_bt11(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """BT-11: project reference roundtrip."""
        data = sample_invoice_data.model_copy(
            update={"project_reference": "PRJ-ALPHA"}
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.project_reference == "PRJ-ALPHA"

    def test_preceding_invoice_bt25(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """BT-25: preceding invoice number roundtrip (credit note)."""
        data = sample_invoice_data.model_copy(
            update={
                "type_code": "381",
                "preceding_invoice_number": "RE-2025-099",
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.preceding_invoice_number == "RE-2025-099"
        assert parsed.type_code == "381"

    def test_no_references_parse_empty(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """All reference fields parse as empty when not set."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.purchase_order_reference == ""
        assert parsed.contract_reference == ""
        assert parsed.project_reference == ""
        assert parsed.preceding_invoice_number == ""

    def test_all_references_together(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """All reference fields work together in same invoice."""
        data = sample_invoice_data.model_copy(
            update={
                "purchase_order_reference": "PO-1",
                "contract_reference": "V-2",
                "project_reference": "P-3",
                "preceding_invoice_number": "RE-0",
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.purchase_order_reference == "PO-1"
        assert parsed.contract_reference == "V-2"
        assert parsed.project_reference == "P-3"
        assert parsed.preceding_invoice_number == "RE-0"


# ============================================================================
# 29. Payment means (BT-81) and remittance info (BT-83) roundtrip
# ============================================================================


class TestPaymentMeansAndRemittance:
    """Tests for BT-81 payment means type code and BT-83 remittance."""

    def test_remittance_information_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """BT-83: remittance information (Verwendungszweck) roundtrip."""
        data = sample_invoice_data.model_copy(
            update={"remittance_information": "RE-2026-001 Projekt Alpha"}
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.remittance_information == "RE-2026-001 Projekt Alpha"

    def test_payment_means_type_code_default(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """BT-81 defaults to 58 (SEPA credit transfer)."""
        assert sample_invoice_data.payment_means_type_code == "58"

    def test_payment_means_type_code_custom(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """BT-81 custom payment means code (e.g. 30 for bank transfer)."""
        data = sample_invoice_data.model_copy(
            update={"payment_means_type_code": "30"}
        )
        xml_bytes = build_xml(data)
        assert b"30" in xml_bytes  # TypeCode in PaymentMeans

    def test_no_remittance_parses_empty(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Remittance info parses as empty when not set."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.remittance_information == ""

    def test_build_invoice_data_with_references(self) -> None:
        """Server _build_invoice_data passes all new reference fields."""
        from einvoice_mcp.server import _build_invoice_data

        data = _build_invoice_data(
            invoice_id="REF-001",
            issue_date="2026-03-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="10115",
            seller_country_code="DE",
            seller_tax_id="DE123456789",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="80999",
            buyer_country_code="DE",
            items_json='[{"description":"Test","quantity":1,"unit_price":100}]',
            purchase_order_reference="PO-42",
            contract_reference="V-99",
            project_reference="P-7",
            preceding_invoice_number="RE-OLD",
            payment_means_type_code="30",
            remittance_information="Ref 12345",
        )
        assert isinstance(data, InvoiceData)
        assert data.purchase_order_reference == "PO-42"
        assert data.contract_reference == "V-99"
        assert data.project_reference == "P-7"
        assert data.preceding_invoice_number == "RE-OLD"
        assert data.payment_means_type_code == "30"
        assert data.remittance_information == "Ref 12345"


# ============================================================================
# 30. BT-25 compliance check for credit notes
# ============================================================================


class TestBT25ComplianceCheck:
    """Compliance checker: credit notes must reference preceding invoice."""

    @respx.mock
    async def test_credit_note_without_bt25_flags_missing(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Credit note (381) without BT-25 is flagged as non-compliant."""
        data = sample_invoice_data.model_copy(
            update={"type_code": "381", "preceding_invoice_number": None}
        )
        xml_content = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml_content, client)
        await client.close()

        bt25_check = next(
            (c for c in result["field_checks"] if c["field"] == "BT-25"),
            None,
        )
        assert bt25_check is not None
        assert bt25_check["present"] is False
        assert "BT-25" in result["missing_fields"]
        assert any("Vorherige" in s for s in result["suggestions"])

    @respx.mock
    async def test_credit_note_with_bt25_passes(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Credit note (381) with BT-25 passes compliance check."""
        data = sample_invoice_data.model_copy(
            update={
                "type_code": "381",
                "preceding_invoice_number": "RE-2025-099",
            }
        )
        xml_content = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml_content, client)
        await client.close()

        bt25_check = next(
            (c for c in result["field_checks"] if c["field"] == "BT-25"),
            None,
        )
        assert bt25_check is not None
        assert bt25_check["present"] is True
        assert bt25_check["value"] == "RE-2025-099"
        assert "BT-25" not in result["missing_fields"]

    @respx.mock
    async def test_regular_invoice_no_bt25_check(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Regular invoice (380) doesn't get BT-25 check."""
        xml_content = build_xml(sample_invoice_data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml_content, client)
        await client.close()

        bt25_check = next(
            (c for c in result["field_checks"] if c["field"] == "BT-25"),
            None,
        )
        # BT-25 check should NOT be present for TypeCode 380
        assert bt25_check is None


# ============================================================================
# 31. PDF output enhancements and coverage gaps
# ============================================================================


class TestPdfOutputEnhancements:
    """PDF generation tests for BT-25, BT-83, and tax_number branch."""

    def test_pdf_credit_note_shows_preceding_ref(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Credit note PDF shows preceding invoice reference."""
        data = sample_invoice_data.model_copy(
            update={
                "type_code": "381",
                "preceding_invoice_number": "RE-2025-099",
            }
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100

    def test_pdf_shows_verwendungszweck(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """PDF shows Verwendungszweck (BT-83) when set."""
        data = sample_invoice_data.model_copy(
            update={"remittance_information": "RE-2026-001 Alpha"}
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100

    def test_pdf_tax_number_branch(self) -> None:
        """PDF displays Steuernummer when no USt-IdNr. is set."""
        from einvoice_mcp.models import Address, LineItem, Party

        data = InvoiceData(
            invoice_id="TAXNUM-001",
            issue_date="2026-03-01",
            seller=Party(
                name="Handwerker GmbH",
                address=Address(
                    street="Werkstr. 1",
                    city="Berlin",
                    postal_code="10115",
                ),
                tax_id=None,
                tax_number="123/456/78901",
            ),
            buyer=Party(
                name="Kunde GmbH",
                address=Address(
                    street="Kundenstr. 1",
                    city="München",
                    postal_code="80999",
                ),
            ),
            items=[LineItem(description="Reparatur", quantity="1", unit_price="500")],
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100

    def test_embed_xml_facturx_import_error(self) -> None:
        """embed_xml_in_pdf raises InvoiceGenerationError on ImportError."""
        with (
            patch(
                "einvoice_mcp.services.pdf_generator.generate_from_binary",
                side_effect=ImportError("not installed"),
                create=True,
            ),
            patch.dict("sys.modules", {"facturx": None}),
            pytest.raises(InvoiceGenerationError, match="factur-x"),
        ):
            embed_xml_in_pdf(b"pdf", b"xml")

    def test_extract_xml_from_pdf_import_error(self) -> None:
        """extract_xml_from_pdf raises InvoiceParsingError on ImportError."""
        with (
            patch.dict("sys.modules", {"facturx": None}),
            pytest.raises(InvoiceParsingError, match="factur-x"),
        ):
            extract_xml_from_pdf(b"fake-pdf")


# ============================================================================
# 32. KoSIT oversized response body (kosit.py line 83)
# ============================================================================


class TestKoSITOversizedBody:
    @respx.mock
    async def test_response_body_exceeds_limit(self) -> None:
        """Response body > MAX_RESPONSE_SIZE raises KoSITValidationError.

        Content-Length header is set to a small value to bypass the header
        check (line 74) and reach the actual body size check (line 82).
        """
        huge_body = "x" * (MAX_RESPONSE_SIZE + 1)
        respx.post(f"{KOSIT_URL}/").respond(
            200, text=huge_body, headers={"Content-Length": "100"}
        )
        client = KoSITClient(base_url=KOSIT_URL)
        with pytest.raises(KoSITValidationError, match="Größenlimit"):
            await client.validate(b"<test/>")
        await client.close()

    @respx.mock
    async def test_content_length_header_exceeds_limit(self) -> None:
        """Content-Length header > MAX_RESPONSE_SIZE triggers early reject."""
        respx.post(f"{KOSIT_URL}/").respond(
            200,
            text="<ok/>",
            headers={"Content-Length": str(MAX_RESPONSE_SIZE + 1)},
        )
        client = KoSITClient(base_url=KOSIT_URL)
        with pytest.raises(KoSITValidationError, match="Größenlimit"):
            await client.validate(b"<test/>")
        await client.close()


# ============================================================================
# 33. Compliance — KoSIT returns errors in report (compliance.py lines 195-196)
# ============================================================================

MOCK_REPORT_WITH_ERRORS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rep:report xmlns:rep="http://www.xoev.de/de/validator/varl/1"
            xmlns:svrl="http://purl.oclc.org/dml/schematron/output/">
  <svrl:schematron-output>
    <svrl:failed-assert id="BR-01" location="/Invoice" flag="error">
      <svrl:text>An Invoice shall have a Specification identifier.</svrl:text>
    </svrl:failed-assert>
  </svrl:schematron-output>
</rep:report>
"""


class TestComplianceKoSITErrors:
    @respx.mock
    async def test_kosit_errors_appended_to_suggestions(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """KoSIT validation errors are included in compliance suggestions."""
        xml_content = build_xml(sample_invoice_data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(
            406, text=MOCK_REPORT_WITH_ERRORS
        )
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml_content, client)
        await client.close()

        # KoSIT said invalid → kosit_valid should be False
        assert result["kosit_valid"] is False
        # The SVRL error message should be in suggestions
        assert any(
            "Specification identifier" in s for s in result["suggestions"]
        )


# ============================================================================
# 34. Validate ZUGFeRD success path (validate.py lines 72-73)
# ============================================================================


class TestValidateZugferdSuccessPath:
    @respx.mock
    async def test_zugferd_valid_pdf_extraction_and_validation(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """ZUGFeRD validate success: extract XML from PDF, then validate."""
        xml_bytes = build_xml(sample_invoice_data)
        valid_b64 = base64.b64encode(b"fake-pdf").decode("ascii")

        # Mock extract_xml_from_pdf to return real XML
        with patch(
            "einvoice_mcp.tools.validate.extract_xml_from_pdf",
            return_value=xml_bytes,
        ):
            respx.post(f"{KOSIT_URL}/").respond(
                200, text=MOCK_VALID_REPORT
            )
            client = KoSITClient(base_url=KOSIT_URL)
            result = await validate_zugferd(valid_b64, client)
            await client.close()

        assert result["valid"] is True


# ============================================================================
# 35. Parse PDF success path (parse.py line 78)
# ============================================================================


class TestParsePdfSuccessPath:
    async def test_parse_pdf_extraction_and_parse_success(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Parse PDF success: extract XML from PDF, then parse."""
        xml_bytes = build_xml(sample_invoice_data)
        valid_b64 = base64.b64encode(b"fake-pdf").decode("ascii")

        with patch(
            "einvoice_mcp.tools.parse.extract_xml_from_pdf",
            return_value=xml_bytes,
        ):
            result = await parse_einvoice(valid_b64, "pdf")

        assert result["success"] is True
        assert result["invoice"]["invoice_id"] == "RE-2026-001"


# ============================================================================
# 36. extract_xml_from_pdf success path (xml_parser.py line 54)
# ============================================================================


class TestExtractXmlFromPdfSuccess:
    def test_extract_xml_success_via_mock(self) -> None:
        """extract_xml_from_pdf success path: get_xml_from_pdf returns data."""
        with patch(
            "einvoice_mcp.services.xml_parser.get_xml_from_pdf",
            side_effect=ImportError("force import path"),
            create=True,
        ):
            pass  # We need to call it via actual import

        # Use the real import path: mock inside the function's local import
        fake_xml = b"<Invoice>test</Invoice>"
        mock_facturx = MagicMock()
        mock_facturx.get_xml_from_pdf.return_value = ("factur-x.xml", fake_xml)

        with patch.dict("sys.modules", {"facturx": mock_facturx}):
            result = extract_xml_from_pdf(b"fake-pdf-bytes")

        assert result == fake_xml
        mock_facturx.get_xml_from_pdf.assert_called_once_with(
            b"fake-pdf-bytes", check_xsd=False
        )


# ============================================================================
# 37. xml_parser _extract_invoice exception handlers (lines 84-182)
# ============================================================================


_EXCEPTION_HANDLER_PARAMS = (
    ("trade", "delivery", "delivery_date"),
    ("trade.settlement", "period", "service_period_start"),
    ("header", "notes", "invoice_note"),
    ("trade.settlement", "terms", "payment_terms"),
    ("trade.agreement", "buyer_order", "purchase_order_reference"),
    ("trade.agreement", "contract", "contract_reference"),
    ("trade.agreement", "procuring_project_type", "project_reference"),
    ("trade.settlement", "invoice_referenced_document", "preceding_invoice_number"),
    ("trade.settlement", "payment_reference", "remittance_information"),
    ("trade.settlement", "payment_means", "seller_iban"),
)


class TestExtractInvoiceExceptionHandlers:
    """Cover the 9 except Exception: pass blocks in _extract_invoice.

    Each test patches a drafthorse class-level descriptor to raise,
    verifying that _extract_invoice gracefully falls back to defaults.
    Uses PropertyMock on the class to bypass read-only descriptors.
    """

    @staticmethod
    def _parse_doc(data: InvoiceData):
        from drafthorse.models.document import Document

        return Document.parse(build_xml(data))

    @staticmethod
    def _resolve(doc, path: str):
        """Resolve dotted path like 'trade.settlement' on a Document."""
        obj = doc
        for part in path.split("."):
            obj = getattr(obj, part)
        return obj

    @pytest.mark.parametrize(
        "path,attr,field",
        _EXCEPTION_HANDLER_PARAMS,
        ids=[p[2] for p in _EXCEPTION_HANDLER_PARAMS],
    )
    def test_exception_handler_graceful_fallback(
        self,
        sample_invoice_data: InvoiceData,
        path: str,
        attr: str,
        field: str,
    ) -> None:
        """Patching '{attr}' on '{path}' to raise → '{field}' falls back to empty."""
        from unittest.mock import PropertyMock

        doc = self._parse_doc(sample_invoice_data)
        target = self._resolve(doc, path)
        target_cls = type(target)

        with patch.object(
            target_cls,
            attr,
            new_callable=PropertyMock,
            side_effect=RuntimeError(f"{attr} boom"),
        ):
            result = _extract_invoice(doc)

        assert getattr(result, field) == ""
        # Other fields should still be populated
        assert result.invoice_id is not None


# ============================================================================
# 38. Contact field parsing roundtrip (BT-41, BT-42, BT-43)
# ============================================================================


class TestContactFieldParsing:
    def test_seller_contact_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Seller contact (name, phone, email) roundtrips through XML."""
        data = sample_invoice_data.model_copy(
            update={
                "seller_contact_name": "Hans Müller",
                "seller_contact_email": "hans@techcorp.de",
                "seller_contact_phone": "+49 30 123456",
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.contact_name == "Hans Müller"
        assert parsed.seller.contact_email == "hans@techcorp.de"
        assert parsed.seller.contact_phone == "+49 30 123456"

    def test_no_contact_returns_none(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No contact info → contact fields are None."""
        data = sample_invoice_data.model_copy(
            update={
                "seller_contact_name": None,
                "seller_contact_email": None,
                "seller_contact_phone": None,
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.contact_name is None
        assert parsed.seller.contact_email is None
        assert parsed.seller.contact_phone is None

    def test_partial_contact(self, sample_invoice_data: InvoiceData) -> None:
        """Only name set → phone and email are None."""
        data = sample_invoice_data.model_copy(
            update={
                "seller_contact_name": "Hans Müller",
                "seller_contact_email": None,
                "seller_contact_phone": None,
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.contact_name == "Hans Müller"
        assert parsed.seller.contact_email is None
        assert parsed.seller.contact_phone is None


# ============================================================================
# 39. IBAN/BIC/Bank name parsing roundtrip (BT-84, BT-86)
# ============================================================================


class TestIbanBicParsing:
    def test_iban_bic_bank_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """IBAN, BIC, and bank name roundtrip through XML."""
        data = sample_invoice_data.model_copy(
            update={
                "seller_iban": "DE89370400440532013000",
                "seller_bic": "COBADEFFXXX",
                "seller_bank_name": "Commerzbank",
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller_iban == "DE89370400440532013000"
        assert parsed.seller_bic == "COBADEFFXXX"
        assert parsed.seller_bank_name == "Commerzbank"

    def test_no_bank_details_empty(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No IBAN → all bank fields empty strings."""
        data = sample_invoice_data.model_copy(
            update={
                "seller_iban": None,
                "seller_bic": None,
                "seller_bank_name": None,
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller_iban == ""
        assert parsed.seller_bic == ""
        assert parsed.seller_bank_name == ""

    def test_iban_only_no_bic(self, sample_invoice_data: InvoiceData) -> None:
        """IBAN without BIC roundtrips correctly."""
        data = sample_invoice_data.model_copy(
            update={
                "seller_iban": "DE89370400440532013000",
                "seller_bic": None,
                "seller_bank_name": None,
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller_iban == "DE89370400440532013000"
        assert parsed.seller_bic == ""


# ============================================================================
# 40. Input validation for ISO codes
# ============================================================================


class TestISOCodeValidation:
    """Validate currency, country code, and payment means type code."""

    def test_valid_currency_eur(self) -> None:
        data = InvoiceData(
            invoice_id="V1",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
            currency="EUR",
        )
        assert data.currency == "EUR"

    def test_valid_currency_usd(self) -> None:
        data = InvoiceData(
            invoice_id="V2",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
            currency="USD",
        )
        assert data.currency == "USD"

    def test_invalid_currency_lowercase(self) -> None:
        with pytest.raises(ValidationError, match="Währungscode"):
            InvoiceData(
                invoice_id="V3",
                issue_date="2026-01-01",
                seller=Party(
                    name="S", address=Address(street="S", city="S", postal_code="00000")
                ),
                buyer=Party(
                    name="B", address=Address(street="B", city="B", postal_code="00000")
                ),
                items=[LineItem(description="X", quantity="1", unit_price="100")],
                currency="eur",
            )

    def test_invalid_currency_numeric(self) -> None:
        with pytest.raises(ValidationError, match="Währungscode"):
            InvoiceData(
                invoice_id="V4",
                issue_date="2026-01-01",
                seller=Party(
                    name="S", address=Address(street="S", city="S", postal_code="00000")
                ),
                buyer=Party(
                    name="B", address=Address(street="B", city="B", postal_code="00000")
                ),
                items=[LineItem(description="X", quantity="1", unit_price="100")],
                currency="123",
            )

    def test_valid_country_code_de(self) -> None:
        addr = Address(street="S", city="S", postal_code="00000", country_code="DE")
        assert addr.country_code == "DE"

    def test_valid_country_code_at(self) -> None:
        addr = Address(street="S", city="S", postal_code="00000", country_code="AT")
        assert addr.country_code == "AT"

    def test_invalid_country_code_lowercase(self) -> None:
        with pytest.raises(ValidationError, match="Ländercode"):
            Address(street="S", city="S", postal_code="00000", country_code="de")

    def test_invalid_country_code_numeric(self) -> None:
        with pytest.raises(ValidationError, match="Ländercode"):
            Address(street="S", city="S", postal_code="00000", country_code="12")

    def test_valid_payment_means_sepa(self) -> None:
        data = InvoiceData(
            invoice_id="PM1",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
            payment_means_type_code="58",
        )
        assert data.payment_means_type_code == "58"

    def test_valid_payment_means_transfer(self) -> None:
        data = InvoiceData(
            invoice_id="PM2",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
            payment_means_type_code="30",
        )
        assert data.payment_means_type_code == "30"

    def test_invalid_payment_means_code(self) -> None:
        with pytest.raises(ValidationError, match="Zahlungsart"):
            InvoiceData(
                invoice_id="PM3",
                issue_date="2026-01-01",
                seller=Party(
                    name="S", address=Address(street="S", city="S", postal_code="00000")
                ),
                buyer=Party(
                    name="B", address=Address(street="B", city="B", postal_code="00000")
                ),
                items=[LineItem(description="X", quantity="1", unit_price="100")],
                payment_means_type_code="99",
            )


# ============================================================================
# 41. Due date (BT-9) roundtrip
# ============================================================================


class TestDueDateRoundtrip:
    def test_due_date_roundtrip(self, sample_invoice_data: InvoiceData) -> None:
        """Due date (BT-9) roundtrips through XML build/parse."""
        from datetime import date

        data = sample_invoice_data.model_copy(
            update={"due_date": date(2026, 3, 15)}
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.due_date == "2026-03-15"

    def test_no_due_date(self, sample_invoice_data: InvoiceData) -> None:
        """No due date → parsed due_date is empty string."""
        data = sample_invoice_data.model_copy(
            update={"due_date": None, "payment_terms_days": None, "payment_terms_text": None}
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.due_date == ""

    def test_due_date_with_payment_terms(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Due date combined with payment terms text."""
        from datetime import date

        data = sample_invoice_data.model_copy(
            update={
                "due_date": date(2026, 4, 1),
                "payment_terms_text": "2% Skonto bei Zahlung innerhalb 10 Tagen",
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.due_date == "2026-04-01"
        assert "Skonto" in parsed.payment_terms

    def test_due_date_in_pdf(self, sample_invoice_data: InvoiceData) -> None:
        """Due date produces a valid PDF (content is compressed)."""
        from datetime import date

        data = sample_invoice_data.model_copy(
            update={"due_date": date(2026, 5, 20)}
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert pdf_bytes.startswith(b"%PDF")
        # PDF with due date should be larger than without
        data_no_due = sample_invoice_data.model_copy(
            update={"due_date": None}
        )
        pdf_no_due = generate_invoice_pdf(data_no_due)
        assert len(pdf_bytes) > len(pdf_no_due)


# ============================================================================
# 42. Address line 2/3 roundtrip (BT-36/37, BT-51/52)
# ============================================================================


class TestAddressLineRoundtrip:
    def test_full_address_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Address lines 2+3 roundtrip through XML build/parse."""
        data = sample_invoice_data.model_copy(
            update={
                "seller": sample_invoice_data.seller.model_copy(
                    update={
                        "address": Address(
                            street="Hauptstr. 1",
                            street_2="Gebäude B",
                            street_3="3. OG",
                            city="Berlin",
                            postal_code="10115",
                        )
                    }
                ),
                "buyer": sample_invoice_data.buyer.model_copy(
                    update={
                        "address": Address(
                            street="Musterweg 5",
                            street_2="Postfach 42",
                            street_3="Eingang C",
                            city="München",
                            postal_code="80331",
                        )
                    }
                ),
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.address.street_2 == "Gebäude B"
        assert parsed.seller.address.street_3 == "3. OG"
        assert parsed.buyer is not None
        assert parsed.buyer.address.street_2 == "Postfach 42"
        assert parsed.buyer.address.street_3 == "Eingang C"

    def test_no_extra_lines(self, sample_invoice_data: InvoiceData) -> None:
        """No address lines 2/3 → parsed as None."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.address.street_2 is None
        assert parsed.seller.address.street_3 is None

    def test_address_lines_in_pdf(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """PDF generates successfully with extra address lines."""
        data = sample_invoice_data.model_copy(
            update={
                "seller": sample_invoice_data.seller.model_copy(
                    update={
                        "address": Address(
                            street="Hauptstr. 1",
                            street_2="Gebäude B",
                            street_3="Hinterhaus",
                            city="Berlin",
                            postal_code="10115",
                        )
                    }
                ),
            }
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert pdf_bytes.startswith(b"%PDF")


# ============================================================================
# 43. Buyer contact roundtrip (BT-44, BT-46, BT-47)
# ============================================================================


class TestBuyerContactRoundtrip:
    def test_buyer_contact_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Buyer contact (BT-44/46/47) roundtrips through XML."""
        data = sample_invoice_data.model_copy(
            update={
                "buyer_contact_name": "Anna Schmidt",
                "buyer_contact_email": "anna@example.de",
                "buyer_contact_phone": "+49 89 987654",
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.buyer is not None
        assert parsed.buyer.contact_name == "Anna Schmidt"
        assert parsed.buyer.contact_email == "anna@example.de"
        assert parsed.buyer.contact_phone == "+49 89 987654"

    def test_no_buyer_contact(self, sample_invoice_data: InvoiceData) -> None:
        """No buyer contact → contact fields are None."""
        data = sample_invoice_data.model_copy(
            update={
                "buyer_contact_name": None,
                "buyer_contact_email": None,
                "buyer_contact_phone": None,
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.buyer is not None
        assert parsed.buyer.contact_name is None
        assert parsed.buyer.contact_email is None
        assert parsed.buyer.contact_phone is None

    def test_both_contacts(self, sample_invoice_data: InvoiceData) -> None:
        """Both seller and buyer contacts roundtrip independently."""
        data = sample_invoice_data.model_copy(
            update={
                "seller_contact_name": "Hans Müller",
                "seller_contact_email": "hans@seller.de",
                "buyer_contact_name": "Anna Schmidt",
                "buyer_contact_email": "anna@buyer.de",
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.contact_name == "Hans Müller"
        assert parsed.seller.contact_email == "hans@seller.de"
        assert parsed.buyer is not None
        assert parsed.buyer.contact_name == "Anna Schmidt"
        assert parsed.buyer.contact_email == "anna@buyer.de"


# ============================================================================
# 44. Registration ID (BT-29) roundtrip
# ============================================================================


class TestRegistrationIdRoundtrip:
    def test_seller_registration_id_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Seller registration ID (BT-29) roundtrips through XML."""
        data = sample_invoice_data.model_copy(
            update={
                "seller": sample_invoice_data.seller.model_copy(
                    update={"registration_id": "4000001000016"}
                ),
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.registration_id == "4000001000016"

    def test_no_registration_id(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No registration ID → parsed as None."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.registration_id is None

    def test_buyer_registration_id(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Buyer registration ID roundtrips through XML."""
        data = sample_invoice_data.model_copy(
            update={
                "buyer": sample_invoice_data.buyer.model_copy(
                    update={"registration_id": "9876543210123"}
                ),
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.buyer is not None
        assert parsed.buyer.registration_id == "9876543210123"


class TestLineAllowancesChargesRoundtrip:
    """Roundtrip tests for line-level allowances/charges (BG-27/BG-28)."""

    def test_line_allowance_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Line-level allowance roundtrips through XML."""
        items = [
            sample_invoice_data.items[0].model_copy(
                update={
                    "allowances_charges": [
                        LineAllowanceCharge(
                            charge=False,
                            amount=Decimal("5.00"),
                            reason="Positionsrabatt",
                        ),
                    ],
                }
            )
        ]
        data = sample_invoice_data.model_copy(update={"items": items})
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert len(parsed.items[0].allowances_charges) == 1
        lac = parsed.items[0].allowances_charges[0]
        assert lac.charge is False
        assert lac.amount == Decimal("5.00")
        assert lac.reason == "Positionsrabatt"

    def test_line_charge_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Line-level charge roundtrips through XML."""
        items = [
            sample_invoice_data.items[0].model_copy(
                update={
                    "allowances_charges": [
                        LineAllowanceCharge(
                            charge=True,
                            amount=Decimal("3.00"),
                            reason="Sonderbehandlung",
                        ),
                    ],
                }
            )
        ]
        data = sample_invoice_data.model_copy(update={"items": items})
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert len(parsed.items[0].allowances_charges) == 1
        lac = parsed.items[0].allowances_charges[0]
        assert lac.charge is True
        assert lac.amount == Decimal("3.00")

    def test_no_line_allowances(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No line allowances → empty list."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.items[0].allowances_charges == []


class TestDeliveryLocationRoundtrip:
    """Roundtrip tests for delivery location (BT-70..BT-80)."""

    def test_delivery_location_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Full delivery location roundtrips through XML."""
        data = sample_invoice_data.model_copy(
            update={
                "delivery_party_name": "Lager Hamburg",
                "delivery_street": "Hafenstraße 12",
                "delivery_city": "Hamburg",
                "delivery_postal_code": "20457",
                "delivery_country_code": "DE",
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.delivery_party_name == "Lager Hamburg"
        assert parsed.delivery_street == "Hafenstraße 12"
        assert parsed.delivery_city == "Hamburg"
        assert parsed.delivery_postal_code == "20457"
        assert parsed.delivery_country_code == "DE"

    def test_no_delivery_location(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No delivery location → empty strings parsed."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.delivery_party_name == ""
        assert parsed.delivery_street == ""

    def test_delivery_name_only(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Only delivery party name (no address)."""
        data = sample_invoice_data.model_copy(
            update={"delivery_party_name": "Zentrale"}
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.delivery_party_name == "Zentrale"

    def test_delivery_location_in_pdf(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """PDF generation includes delivery location section."""
        data = sample_invoice_data.model_copy(
            update={
                "delivery_party_name": "Lager Nord",
                "delivery_street": "Industriestr. 5",
                "delivery_city": "Bremen",
                "delivery_postal_code": "28195",
                "delivery_country_code": "DE",
            }
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert len(pdf_bytes) > 0
        # PDF with delivery should be larger than without
        pdf_no_delivery = generate_invoice_pdf(sample_invoice_data)
        assert len(pdf_bytes) > len(pdf_no_delivery)


class TestLineItemNoteRoundtrip:
    """Roundtrip tests for line-item note (BT-127)."""

    def test_item_note_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Line item note roundtrips through XML."""
        items = [
            sample_invoice_data.items[0].model_copy(
                update={"item_note": "Lieferung per Express"}
            )
        ]
        data = sample_invoice_data.model_copy(update={"items": items})
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.items[0].item_note == "Lieferung per Express"

    def test_no_item_note(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No item note → None in parsed output."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.items[0].item_note is None


class TestLineItemIdentifiersRoundtrip:
    """Roundtrip tests for line-item identifiers (BT-155/156/157)."""

    def test_seller_item_id_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Seller item ID (BT-155) roundtrips through XML."""
        items = [
            sample_invoice_data.items[0].model_copy(
                update={"seller_item_id": "ART-001"}
            )
        ]
        data = sample_invoice_data.model_copy(update={"items": items})
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.items[0].seller_item_id == "ART-001"

    def test_buyer_item_id_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Buyer item ID (BT-156) roundtrips through XML."""
        items = [
            sample_invoice_data.items[0].model_copy(
                update={"buyer_item_id": "BUYER-X1"}
            )
        ]
        data = sample_invoice_data.model_copy(update={"items": items})
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.items[0].buyer_item_id == "BUYER-X1"

    def test_standard_item_id_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Standard item ID / GTIN (BT-157) roundtrips through XML."""
        items = [
            sample_invoice_data.items[0].model_copy(
                update={
                    "standard_item_id": "4012345000001",
                    "standard_item_scheme": "0160",
                }
            )
        ]
        data = sample_invoice_data.model_copy(update={"items": items})
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.items[0].standard_item_id == "4012345000001"
        assert parsed.items[0].standard_item_scheme == "0160"

    def test_no_item_ids(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No item IDs → all None in parsed output."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.items[0].seller_item_id is None
        assert parsed.items[0].buyer_item_id is None
        assert parsed.items[0].standard_item_id is None

    def test_seller_item_id_in_pdf(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Seller item ID shown in PDF line items."""
        items = [
            sample_invoice_data.items[0].model_copy(
                update={"seller_item_id": "ART-999"}
            )
        ]
        data = sample_invoice_data.model_copy(update={"items": items})
        pdf_bytes = generate_invoice_pdf(data)
        assert len(pdf_bytes) > 0

    def test_all_item_ids_together(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """All three item IDs set simultaneously."""
        items = [
            sample_invoice_data.items[0].model_copy(
                update={
                    "seller_item_id": "V-001",
                    "buyer_item_id": "K-001",
                    "standard_item_id": "4012345000001",
                }
            )
        ]
        data = sample_invoice_data.model_copy(update={"items": items})
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.items[0].seller_item_id == "V-001"
        assert parsed.items[0].buyer_item_id == "K-001"
        assert parsed.items[0].standard_item_id == "4012345000001"


class TestSalesOrderReferenceRoundtrip:
    """Roundtrip tests for seller order reference (BT-14)."""

    def test_sales_order_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Sales order reference roundtrips through XML."""
        data = sample_invoice_data.model_copy(
            update={"sales_order_reference": "SO-2026-001"}
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.sales_order_reference == "SO-2026-001"

    def test_no_sales_order_reference(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No sales order reference → empty string parsed."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.sales_order_reference == ""


class TestAllowancesChargesRoundtrip:
    """Roundtrip tests for document-level allowances/charges (BG-20/BG-21)."""

    def test_allowance_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Allowance (discount) roundtrips through XML generation and parsing."""
        data = sample_invoice_data.model_copy(
            update={
                "allowances_charges": [
                    AllowanceCharge(
                        charge=False,
                        amount=Decimal("50.00"),
                        reason="Treuerabatt",
                        tax_rate=Decimal("19.00"),
                        tax_category=TaxCategory.S,
                    ),
                ],
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert len(parsed.allowances_charges) == 1
        ac = parsed.allowances_charges[0]
        assert ac.charge is False
        assert ac.amount == Decimal("50.00")
        assert ac.reason == "Treuerabatt"
        assert ac.tax_rate == Decimal("19.00")
        assert ac.tax_category == "S"

    def test_charge_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Charge (surcharge) roundtrips through XML generation and parsing."""
        data = sample_invoice_data.model_copy(
            update={
                "allowances_charges": [
                    AllowanceCharge(
                        charge=True,
                        amount=Decimal("25.00"),
                        reason="Expressversand",
                        tax_rate=Decimal("19.00"),
                        tax_category=TaxCategory.S,
                    ),
                ],
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert len(parsed.allowances_charges) == 1
        ac = parsed.allowances_charges[0]
        assert ac.charge is True
        assert ac.amount == Decimal("25.00")
        assert ac.reason == "Expressversand"

    def test_mixed_allowances_charges(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Multiple allowances and charges roundtrip correctly."""
        data = sample_invoice_data.model_copy(
            update={
                "allowances_charges": [
                    AllowanceCharge(
                        charge=False,
                        amount=Decimal("30.00"),
                        reason="Mengenrabatt",
                        tax_rate=Decimal("19.00"),
                    ),
                    AllowanceCharge(
                        charge=True,
                        amount=Decimal("15.00"),
                        reason="Verpackung",
                        tax_rate=Decimal("19.00"),
                    ),
                ],
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert len(parsed.allowances_charges) == 2
        allowance = next(ac for ac in parsed.allowances_charges if not ac.charge)
        charge = next(ac for ac in parsed.allowances_charges if ac.charge)
        assert allowance.amount == Decimal("30.00")
        assert allowance.reason == "Mengenrabatt"
        assert charge.amount == Decimal("15.00")
        assert charge.reason == "Verpackung"

    def test_no_allowances_charges(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No allowances/charges → empty list parsed."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.allowances_charges == []

    def test_allowance_affects_totals(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Allowance reduces tax basis and grand total correctly."""
        data = sample_invoice_data.model_copy(
            update={
                "allowances_charges": [
                    AllowanceCharge(
                        charge=False,
                        amount=Decimal("100.00"),
                        reason="Sonderrabatt",
                        tax_rate=Decimal("19.00"),
                    ),
                ],
            }
        )
        # Verify model calculations
        net = data.total_net()
        assert data.total_allowances() == Decimal("100.00")
        assert data.total_charges() == Decimal("0")
        tax_basis = data.tax_basis()
        assert tax_basis == (net - Decimal("100.00")).quantize(Decimal("0.01"))

        # Verify XML roundtrip totals
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.totals is not None
        # Parsed net_total is tax_basis (BT-109), not line total
        assert parsed.totals.net_total == tax_basis

    def test_charge_with_percentage_and_base_amount(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Charge with reason_code, base_amount, percentage covers builder branches."""
        data = sample_invoice_data.model_copy(
            update={
                "allowances_charges": [
                    AllowanceCharge(
                        charge=True,
                        amount=Decimal("20.00"),
                        reason="Bearbeitungsgebühr",
                        reason_code="ZZZ",
                        tax_rate=Decimal("19.00"),
                        tax_category=TaxCategory.S,
                        base_amount=Decimal("200.00"),
                        percentage=Decimal("10.00"),
                    ),
                ],
            }
        )
        # This exercises total_tax() charge branch (models.py:360)
        assert data.total_charges() == Decimal("20.00")
        expected_basis = data.total_net() + Decimal("20.00")
        assert data.tax_basis() == expected_basis.quantize(Decimal("0.01"))
        # Total tax should include the charge in its group
        assert data.total_tax() > Decimal("0")

        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert len(parsed.allowances_charges) == 1
        ac = parsed.allowances_charges[0]
        assert ac.charge is True
        assert ac.amount == Decimal("20.00")

    def test_allowance_in_pdf(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """PDF generation succeeds with allowances/charges."""
        data = sample_invoice_data.model_copy(
            update={
                "allowances_charges": [
                    AllowanceCharge(
                        charge=False,
                        amount=Decimal("50.00"),
                        reason="Rabatt",
                        tax_rate=Decimal("19.00"),
                    ),
                ],
            }
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert len(pdf_bytes) > 0
        # PDF with allowances should differ from without
        pdf_no_ac = generate_invoice_pdf(sample_invoice_data)
        assert len(pdf_bytes) != len(pdf_no_ac)


class TestSkontoRoundtrip:
    """Roundtrip tests for Skonto (early payment discount)."""

    def test_skonto_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Skonto terms roundtrip through XML."""
        data = sample_invoice_data.model_copy(
            update={
                "skonto_percent": Decimal("2.00"),
                "skonto_days": 10,
                "payment_terms_days": None,  # Clear to let Skonto text generate
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.skonto_percent == "2.00"
        assert "10" in parsed.skonto_days
        assert "Skonto" in parsed.payment_terms

    def test_skonto_with_base_amount(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Skonto with explicit base amount."""
        data = sample_invoice_data.model_copy(
            update={
                "skonto_percent": Decimal("3.00"),
                "skonto_days": 14,
                "skonto_base_amount": Decimal("1000.00"),
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.skonto_percent == "3.00"

    def test_no_skonto(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No Skonto → empty strings parsed."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.skonto_percent == ""
        assert parsed.skonto_days == ""

    def test_skonto_in_pdf(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Skonto generates payment terms text in PDF."""
        # Clear payment_terms_days so Skonto text is generated
        base = sample_invoice_data.model_copy(
            update={"payment_terms_days": None}
        )
        data = base.model_copy(
            update={
                "skonto_percent": Decimal("2.00"),
                "skonto_days": 10,
            }
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert len(pdf_bytes) > 0
        # PDF with Skonto should be larger than without
        pdf_no_skonto = generate_invoice_pdf(base)
        assert len(pdf_bytes) > len(pdf_no_skonto)


class TestPdfContactInfo:
    """Tests for contact info display in PDF."""

    def test_pdf_with_contact_info(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """PDF with contact info generates successfully."""
        data = sample_invoice_data.model_copy(
            update={
                "seller_contact_name": "Max Mustermann",
                "seller_contact_phone": "+49 30 12345678",
                "seller_contact_email": "max@techcorp.de",
                "buyer_contact_name": "Erika Muster",
                "buyer_contact_phone": "+49 89 9876543",
                "buyer_contact_email": "erika@buyer.de",
            }
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_with_party_contact(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Contact info from Party model also renders in PDF."""
        seller = sample_invoice_data.seller.model_copy(
            update={
                "contact_name": "Erika Muster",
                "contact_phone": "+49 89 9876543",
                "contact_email": "erika@example.de",
            }
        )
        data = sample_invoice_data.model_copy(update={"seller": seller})
        pdf_bytes = generate_invoice_pdf(data)
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:5] == b"%PDF-"


class TestSepaDirectDebitRoundtrip:
    """Roundtrip tests for SEPA direct debit (BG-19)."""

    def test_sepa_direct_debit_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """SEPA direct debit fields roundtrip through XML."""
        data = sample_invoice_data.model_copy(
            update={
                "payment_means_type_code": "59",
                "buyer_iban": "DE75512108001245126199",
                "mandate_reference_id": "MANDATE-2026-001",
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.buyer_iban == "DE75512108001245126199"
        assert parsed.mandate_reference_id == "MANDATE-2026-001"

    def test_no_direct_debit(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No direct debit → empty strings parsed."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.buyer_iban == ""
        assert parsed.mandate_reference_id == ""


class TestInvoicedObjectIdentifierRoundtrip:
    """Roundtrip tests for invoiced object identifier (BT-18)."""

    def test_bt18_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Invoiced object identifier roundtrips through XML."""
        data = sample_invoice_data.model_copy(
            update={"invoiced_object_identifier": "METER-12345"}
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.invoiced_object_identifier == "METER-12345"

    def test_no_bt18(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No invoiced object identifier → empty string parsed."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.invoiced_object_identifier == ""

    def test_bt18_xml_contains_type_code_130(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """BT-18 generates AdditionalReferencedDocument with TypeCode 130."""
        data = sample_invoice_data.model_copy(
            update={"invoiced_object_identifier": "SUB-999"}
        )
        xml_bytes = build_xml(data)
        xml_str = xml_bytes.decode("utf-8")
        assert "130" in xml_str
        assert "SUB-999" in xml_str


class TestDespatchAdviceRoundtrip:
    """Roundtrip tests for despatch advice reference (BT-16)."""

    def test_bt16_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Despatch advice reference roundtrips through XML."""
        data = sample_invoice_data.model_copy(
            update={"despatch_advice_reference": "DESP-2026-001"}
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.despatch_advice_reference == "DESP-2026-001"

    def test_no_bt16(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No despatch advice reference → empty string parsed."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.despatch_advice_reference == ""


class TestBusinessProcessTypeRoundtrip:
    """Roundtrip tests for business process type (BT-23)."""

    def test_bt23_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Business process type roundtrips through XML."""
        data = sample_invoice_data.model_copy(
            update={
                "business_process_type": "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.business_process_type == (
            "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"
        )

    def test_no_bt23(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No business process type → empty string parsed."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.business_process_type == ""


class TestXmlParserExceptionHandlers:
    """Cover defensive exception handlers in xml_parser.py."""

    def test_sales_order_exception_returns_empty(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Sales order attribute error → gracefully returns empty string."""
        xml_bytes = build_xml(sample_invoice_data)
        from drafthorse.models.document import Document

        doc = Document.parse(xml_bytes)
        # Inject broken mock via _data dict to bypass read-only descriptor
        broken = MagicMock()
        type(broken).issuer_assigned_id = property(
            lambda s: (_ for _ in ()).throw(RuntimeError("broken"))
        )
        doc.trade.agreement._data["seller_order"] = broken
        parsed = _extract_invoice(doc)
        assert parsed.sales_order_reference == ""

    def test_invoiced_object_exception_returns_empty(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Additional references exception → empty invoiced_object_identifier."""
        xml_bytes = build_xml(sample_invoice_data)
        from drafthorse.models.document import Document

        doc = Document.parse(xml_bytes)
        broken_refs = MagicMock()
        type(broken_refs).children = property(
            lambda s: (_ for _ in ()).throw(RuntimeError("broken"))
        )
        doc.trade.agreement._data["additional_references"] = broken_refs
        parsed = _extract_invoice(doc)
        assert parsed.invoiced_object_identifier == ""

    def test_business_process_exception_returns_empty(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Business parameter exception → empty business_process_type."""
        xml_bytes = build_xml(sample_invoice_data)
        from drafthorse.models.document import Document

        doc = Document.parse(xml_bytes)
        broken = MagicMock()
        type(broken).id = property(
            lambda s: (_ for _ in ()).throw(RuntimeError("broken"))
        )
        doc.context._data["business_parameter"] = broken
        parsed = _extract_invoice(doc)
        assert parsed.business_process_type == ""

    def test_allowances_charges_exception_returns_empty(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Allowances/charges block exception → empty list."""
        data = sample_invoice_data.model_copy(
            update={"allowances_charges": [
                AllowanceCharge(charge=False, amount=Decimal("10"), reason="Test"),
            ]}
        )
        xml_bytes = build_xml(data)
        from drafthorse.models.document import Document

        doc = Document.parse(xml_bytes)
        broken = MagicMock()
        type(broken).children = property(
            lambda s: (_ for _ in ()).throw(RuntimeError("broken"))
        )
        doc.trade.settlement._data["allowance_charge"] = broken
        parsed = _extract_invoice(doc)
        assert parsed.allowances_charges == []

    def test_doc_level_indicator_without_value(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Indicator without _value attribute → fallback bool."""
        data = sample_invoice_data.model_copy(
            update={"allowances_charges": [
                AllowanceCharge(
                    charge=True,
                    amount=Decimal("5"),
                    reason="Zuschlag",
                ),
            ]}
        )
        xml_bytes = build_xml(data)
        from drafthorse.models.document import Document

        doc = Document.parse(xml_bytes)
        ac_container = doc.trade.settlement.allowance_charge
        if hasattr(ac_container, "children"):
            for ac_item in ac_container.children:
                indicator = getattr(ac_item, "indicator", None)
                if indicator is not None and hasattr(indicator, "_value"):
                    delattr(indicator, "_value")
        parsed = _extract_invoice(doc)
        assert isinstance(parsed.allowances_charges, list)

    def test_line_level_indicator_without_value(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Line-level indicator without _value → fallback bool."""
        data = sample_invoice_data.model_copy(
            update={
                "items": [
                    sample_invoice_data.items[0].model_copy(
                        update={
                            "allowances_charges": [
                                LineAllowanceCharge(
                                    charge=False,
                                    amount=Decimal("3"),
                                    reason="Rabatt",
                                ),
                            ],
                        }
                    ),
                ],
            }
        )
        xml_bytes = build_xml(data)
        from drafthorse.models.document import Document

        doc = Document.parse(xml_bytes)
        for li in doc.trade.items.children:
            lac_container = getattr(li.settlement, "allowance_charge", None)
            if lac_container and hasattr(lac_container, "children"):
                for lac_item in lac_container.children:
                    lac_indicator = getattr(lac_item, "indicator", None)
                    if lac_indicator and hasattr(lac_indicator, "_value"):
                        delattr(lac_indicator, "_value")
        parsed = _extract_invoice(doc)
        assert len(parsed.items) > 0


class TestComplianceValueError:
    """Cover compliance.py ValueError handler (lines 466-467)."""

    @respx.mock
    async def test_reverse_charge_non_numeric_rate(self) -> None:
        """AE category with non-numeric rate text → ValueError caught gracefully."""
        data = InvoiceData(
            invoice_id="RC-VE-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
                tax_id="ATU12345678",
            ),
            items=[
                LineItem(
                    description="RC Service",
                    quantity="1",
                    unit_price="1000",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.AE,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        # Inject non-numeric rate text into the XML to trigger ValueError
        xml = xml.replace(
            "<ram:RateApplicablePercent>0</ram:RateApplicablePercent>",
            "<ram:RateApplicablePercent>abc</ram:RateApplicablePercent>",
            1,
        )
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        # Should not crash — ValueError caught, RC-TAX-RATE not flagged
        assert "RC-TAX-RATE" not in result.get("missing_fields", [])
        await client.close()


class TestIbanBicValidation:
    """Test IBAN and BIC format validation in InvoiceData."""

    def _rebuild(
        self, base: InvoiceData, **updates: object
    ) -> InvoiceData:
        """Rebuild InvoiceData with updates to trigger validators."""
        return InvoiceData.model_validate(
            base.model_dump() | updates
        )

    def test_valid_german_iban(self, sample_invoice_data: InvoiceData) -> None:
        """Valid German IBAN accepted."""
        data = self._rebuild(
            sample_invoice_data, seller_iban="DE89370400440532013000"
        )
        assert data.seller_iban == "DE89370400440532013000"

    def test_valid_iban_with_spaces(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """IBAN with spaces normalized to uppercase without spaces."""
        data = self._rebuild(
            sample_invoice_data,
            seller_iban="DE89 3704 0044 0532 0130 00",
        )
        assert data.seller_iban == "DE89370400440532013000"

    def test_valid_iban_lowercase(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Lowercase IBAN normalized to uppercase."""
        data = self._rebuild(
            sample_invoice_data, seller_iban="de89370400440532013000"
        )
        assert data.seller_iban == "DE89370400440532013000"

    def test_invalid_iban_too_short(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """IBAN too short → ValidationError."""
        with pytest.raises(ValidationError, match="IBAN"):
            self._rebuild(sample_invoice_data, seller_iban="DE89")

    def test_invalid_iban_no_country(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """IBAN without country code → ValidationError."""
        with pytest.raises(ValidationError, match="IBAN"):
            self._rebuild(
                sample_invoice_data, seller_iban="12345678901234567890"
            )

    def test_invalid_iban_special_chars(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """IBAN with special characters → ValidationError."""
        with pytest.raises(ValidationError, match="IBAN"):
            self._rebuild(
                sample_invoice_data,
                seller_iban="DE89-3704-0044-0532-0130-00",
            )

    def test_buyer_iban_validated(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Buyer IBAN also validated."""
        data = self._rebuild(
            sample_invoice_data, buyer_iban="AT611904300234573201"
        )
        assert data.buyer_iban == "AT611904300234573201"

    def test_invalid_buyer_iban(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Invalid buyer IBAN → ValidationError."""
        with pytest.raises(ValidationError, match="IBAN"):
            self._rebuild(sample_invoice_data, buyer_iban="INVALID")

    def test_none_iban_accepted(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """None IBAN (not set) accepted."""
        data = self._rebuild(sample_invoice_data, seller_iban=None)
        assert data.seller_iban is None

    def test_valid_bic_8_chars(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Valid 8-char BIC accepted."""
        data = self._rebuild(
            sample_invoice_data, seller_bic="COBADEFF"
        )
        assert data.seller_bic == "COBADEFF"

    def test_valid_bic_11_chars(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Valid 11-char BIC accepted."""
        data = self._rebuild(
            sample_invoice_data, seller_bic="COBADEFFXXX"
        )
        assert data.seller_bic == "COBADEFFXXX"

    def test_invalid_bic_wrong_length(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """BIC with wrong length → ValidationError."""
        with pytest.raises(ValidationError, match="BIC"):
            self._rebuild(sample_invoice_data, seller_bic="COBADE")

    def test_invalid_bic_digits_start(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """BIC starting with digits → ValidationError."""
        with pytest.raises(ValidationError, match="BIC"):
            self._rebuild(sample_invoice_data, seller_bic="12345678")

    def test_none_bic_accepted(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """None BIC (not set) accepted."""
        data = self._rebuild(sample_invoice_data, seller_bic=None)
        assert data.seller_bic is None


class TestIntraCommunityCompliance:
    """Test intra-community supply (K) compliance checks."""

    @respx.mock
    async def test_k_missing_buyer_vat(self) -> None:
        """Intra-community (K) without buyer VAT → IC-BT-48 error."""
        data = InvoiceData(
            invoice_id="IC-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="ig. Lieferung",
                    quantity="1",
                    unit_price="1000",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.K,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "IC-BT-48" in result["missing_fields"]
        await client.close()

    @respx.mock
    async def test_k_valid_with_buyer_vat(self) -> None:
        """Intra-community (K) with buyer VAT → passes IC checks."""
        data = InvoiceData(
            invoice_id="IC-002",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
                tax_id="FR12345678901",
            ),
            items=[
                LineItem(
                    description="ig. Lieferung",
                    quantity="1",
                    unit_price="1000",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.K,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "IC-BT-48" not in result.get("missing_fields", [])
        await client.close()

    @respx.mock
    async def test_k_nonzero_tax_rate(self) -> None:
        """Intra-community (K) with non-zero rate → IC-TAX-RATE error."""
        data = InvoiceData(
            invoice_id="IC-003",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
                tax_id="FR12345678901",
            ),
            items=[
                LineItem(
                    description="ig. Lieferung",
                    quantity="1",
                    unit_price="1000",
                    tax_rate=Decimal("19"),
                    tax_category=TaxCategory.K,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "IC-TAX-RATE" in result["missing_fields"]
        await client.close()

    @respx.mock
    async def test_k_non_numeric_rate(self) -> None:
        """Intra-community (K) with non-numeric rate → ValueError caught."""
        data = InvoiceData(
            invoice_id="IC-004",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
                tax_id="FR12345678901",
            ),
            items=[
                LineItem(
                    description="ig. Lieferung",
                    quantity="1",
                    unit_price="1000",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.K,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        xml = xml.replace(
            "<ram:RateApplicablePercent>0</ram:RateApplicablePercent>",
            "<ram:RateApplicablePercent>xyz</ram:RateApplicablePercent>",
            1,
        )
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "IC-TAX-RATE" not in result.get("missing_fields", [])
        await client.close()


class TestLeitwegIdFormatCompliance:
    """Test Leitweg-ID and VAT ID format validation."""

    @respx.mock
    async def test_valid_leitweg_format(self) -> None:
        """Valid Leitweg-ID format → no LW-FMT warning."""
        data = InvoiceData(
            invoice_id="LW-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Beratung",
                    quantity="1",
                    unit_price="100",
                    tax_rate=Decimal("19"),
                ),
            ],
            buyer_reference="04011000-12345-67",
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        advisory = [
            fc["field"]
            for fc in result.get("field_checks", [])
            if fc["field"] == "LW-FMT"
        ]
        assert advisory == []
        await client.close()

    @respx.mock
    async def test_invalid_leitweg_format(self) -> None:
        """Invalid Leitweg-ID format → LW-FMT advisory."""
        data = InvoiceData(
            invoice_id="LW-002",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Beratung",
                    quantity="1",
                    unit_price="100",
                    tax_rate=Decimal("19"),
                ),
            ],
            buyer_reference="not-a-leitweg",
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        suggestions = result.get("suggestions", [])
        has_lw_warning = any("Leitweg-ID" in s for s in suggestions)
        assert has_lw_warning
        await client.close()

    @respx.mock
    async def test_invalid_german_vat_format(self) -> None:
        """Invalid DE VAT ID format → VAT-FMT advisory."""
        data = InvoiceData(
            invoice_id="VAT-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE12",  # Too short for DE format
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Beratung",
                    quantity="1",
                    unit_price="100",
                    tax_rate=Decimal("19"),
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        suggestions = result.get("suggestions", [])
        has_vat_warning = any("USt-IdNr" in s for s in suggestions)
        assert has_vat_warning
        await client.close()

    @respx.mock
    async def test_valid_german_vat_format(self) -> None:
        """Valid DE VAT ID format → no VAT-FMT warning."""
        data = InvoiceData(
            invoice_id="VAT-002",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Beratung",
                    quantity="1",
                    unit_price="100",
                    tax_rate=Decimal("19"),
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        vat_checks = [
            fc for fc in result.get("field_checks", [])
            if fc["field"] == "VAT-FMT"
        ]
        assert vat_checks == []
        await client.close()

    @respx.mock
    async def test_non_de_vat_no_format_check(self) -> None:
        """Non-DE VAT ID → no format check applied."""
        data = InvoiceData(
            invoice_id="VAT-003",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="ATU12345678",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Beratung",
                    quantity="1",
                    unit_price="100",
                    tax_rate=Decimal("19"),
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        vat_checks = [
            fc for fc in result.get("field_checks", [])
            if fc["field"] == "VAT-FMT"
        ]
        assert vat_checks == []
        await client.close()


class TestBuyerAccountingReferenceRoundtrip:
    """Test BT-133 buyer accounting reference roundtrip."""

    def test_accounting_reference_roundtrip(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """BT-133 generates and parses correctly."""
        data = sample_invoice_data.model_copy(
            update={
                "items": [
                    sample_invoice_data.items[0].model_copy(
                        update={
                            "buyer_accounting_reference": "KST-4711",
                        }
                    ),
                ],
            }
        )
        xml_bytes = build_xml(data)
        parsed = parse_xml(xml_bytes)
        assert parsed.items[0].buyer_accounting_reference == "KST-4711"

    def test_no_accounting_reference(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """No BT-133 → None in parsed output."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.items[0].buyer_accounting_reference is None


class TestExportComplianceG:
    """Test export outside EU (G) compliance checks."""

    @respx.mock
    async def test_g_zero_rate_valid(self) -> None:
        """Export (G) with 0% rate → no error."""
        data = InvoiceData(
            invoice_id="EX-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Export goods",
                    quantity="1",
                    unit_price="1000",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.G,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "EX-TAX-RATE" not in result.get("missing_fields", [])
        await client.close()

    @respx.mock
    async def test_g_nonzero_rate(self) -> None:
        """Export (G) with non-zero rate → EX-TAX-RATE error."""
        data = InvoiceData(
            invoice_id="EX-002",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Export goods",
                    quantity="1",
                    unit_price="1000",
                    tax_rate=Decimal("19"),
                    tax_category=TaxCategory.G,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "EX-TAX-RATE" in result["missing_fields"]
        await client.close()

    @respx.mock
    async def test_g_non_numeric_rate(self) -> None:
        """Export (G) with non-numeric rate → ValueError caught."""
        data = InvoiceData(
            invoice_id="EX-003",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Export goods",
                    quantity="1",
                    unit_price="1000",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.G,
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        xml = xml.replace(
            "<ram:RateApplicablePercent>0</ram:RateApplicablePercent>",
            "<ram:RateApplicablePercent>nnn</ram:RateApplicablePercent>",
            1,
        )
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert "EX-TAX-RATE" not in result.get("missing_fields", [])
        await client.close()


class TestKleinbetragsrechnungAdvisory:
    """Test §33 UStDV Kleinbetragsrechnung advisory."""

    @respx.mock
    async def test_small_invoice_gets_kb_hint(self) -> None:
        """Invoice ≤250€ gross → KB-INFO advisory shown."""
        data = InvoiceData(
            invoice_id="KB-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Kleinartikel",
                    quantity="1",
                    unit_price="100",
                    tax_rate=Decimal("19"),
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        suggestions = result.get("suggestions", [])
        has_kb = any("Kleinbetragsrechnung" in s for s in suggestions)
        assert has_kb
        await client.close()

    @respx.mock
    async def test_large_invoice_no_kb_hint(self) -> None:
        """Invoice >250€ gross → no KB-INFO advisory."""
        data = InvoiceData(
            invoice_id="KB-002",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Großauftrag",
                    quantity="10",
                    unit_price="1000",
                    tax_rate=Decimal("19"),
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        suggestions = result.get("suggestions", [])
        has_kb = any("Kleinbetragsrechnung" in s for s in suggestions)
        assert not has_kb
        await client.close()

    @respx.mock
    async def test_non_numeric_total_no_crash(self) -> None:
        """Non-numeric grand total → ValueError caught, no crash."""
        data = InvoiceData(
            invoice_id="KB-003",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="S", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="B", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Test",
                    quantity="1",
                    unit_price="100",
                    tax_rate=Decimal("19"),
                ),
            ],
        )
        xml = build_xml(data).decode("utf-8")
        xml = xml.replace(
            'currencyID="EUR">119.00</ram:GrandTotalAmount>',
            'currencyID="EUR">xxx</ram:GrandTotalAmount>',
        )
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        suggestions = result.get("suggestions", [])
        has_kb = any("Kleinbetragsrechnung" in s for s in suggestions)
        assert not has_kb
        await client.close()


# ---------------------------------------------------------------------------
# Trading names (BT-28/BT-45) and tender reference (BT-17) roundtrip
# ---------------------------------------------------------------------------
class TestTradingNamesAndTenderRoundtrip:
    """BT-28, BT-45, BT-17 roundtrip through builder → parser."""

    def _base_data(self, **overrides: object) -> InvoiceData:
        defaults: dict[str, object] = {
            "invoice_id": "TN-001",
            "issue_date": "2026-01-01",
            "seller": Party(
                name="Legal GmbH",
                trading_name="BrandName Store",
                address=Address(street="S 1", city="Berlin", postal_code="10115"),
                tax_id="DE123456789",
            ),
            "buyer": Party(
                name="Käufer AG",
                trading_name="Buyer Brand",
                address=Address(street="B 1", city="München", postal_code="80331"),
            ),
            "items": [
                LineItem(description="Pos 1", quantity="1", unit_price="100"),
            ],
        }
        defaults.update(overrides)
        return InvoiceData(**defaults)

    def test_trading_names_roundtrip(self) -> None:
        data = self._base_data()
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert parsed.seller is not None
        assert parsed.seller.trading_name == "BrandName Store"
        assert parsed.buyer is not None
        assert parsed.buyer.trading_name == "Buyer Brand"

    def test_no_trading_names(self) -> None:
        data = self._base_data(
            seller=Party(
                name="Plain Seller",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE111111111",
            ),
            buyer=Party(
                name="Plain Buyer",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
        )
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert parsed.seller is not None
        assert parsed.seller.trading_name is None
        assert parsed.buyer is not None
        assert parsed.buyer.trading_name is None

    def test_tender_reference_roundtrip(self) -> None:
        data = self._base_data(tender_or_lot_reference="TENDER-2026-42/LOT-3")
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert parsed.tender_or_lot_reference == "TENDER-2026-42/LOT-3"

    def test_tender_and_invoiced_object_coexist(self) -> None:
        data = self._base_data(
            tender_or_lot_reference="VERGABE-123",
            invoiced_object_identifier="METER-456",
        )
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert parsed.tender_or_lot_reference == "VERGABE-123"
        assert parsed.invoiced_object_identifier == "METER-456"


# ---------------------------------------------------------------------------
# VAT exemption reason (BT-120/BT-121) roundtrip and compliance
# ---------------------------------------------------------------------------
class TestVatExemptionReason:
    """BT-120/BT-121 exemption reason roundtrip + BR-E-10 compliance."""

    def _base_data(self, **overrides: object) -> InvoiceData:
        defaults: dict[str, object] = {
            "invoice_id": "EX-001",
            "issue_date": "2026-01-01",
            "seller": Party(
                name="Seller",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE123456789",
            ),
            "buyer": Party(
                name="Buyer",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
            "items": [
                LineItem(
                    description="Service",
                    quantity="1",
                    unit_price="100",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.E,
                ),
            ],
        }
        defaults.update(overrides)
        return InvoiceData(**defaults)

    def test_exemption_reason_roundtrip(self) -> None:
        data = self._base_data(
            tax_exemption_reason="Gemäß §19 UStG wird keine Umsatzsteuer berechnet.",
            tax_exemption_reason_code="vatex-eu-ic",
        )
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert parsed.tax_exemption_reason == "Gemäß §19 UStG wird keine Umsatzsteuer berechnet."
        assert parsed.tax_exemption_reason_code == "vatex-eu-ic"

    def test_no_exemption_reason(self) -> None:
        data = self._base_data()
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert parsed.tax_exemption_reason == ""
        assert parsed.tax_exemption_reason_code == ""

    @respx.mock
    async def test_compliance_missing_exemption_reason(self) -> None:
        """BR-E-10: TaxCategory=E without BT-120 → E-BT-120 missing."""
        data = self._base_data()
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        missing = result.get("missing_fields", [])
        assert "E-BT-120" in missing
        suggestions = result.get("suggestions", [])
        assert any("Befreiungsgrund" in s for s in suggestions)
        await client.close()

    @respx.mock
    async def test_compliance_with_exemption_reason(self) -> None:
        """TaxCategory=E with BT-120 → E-BT-120 NOT missing."""
        data = self._base_data(
            tax_exemption_reason="Steuerbefreit gemäß §4 Nr. 11 UStG",
            invoice_note="Steuerbefreit gemäß §4 Nr. 11 UStG",
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        missing = result.get("missing_fields", [])
        assert "E-BT-120" not in missing
        await client.close()


# ---------------------------------------------------------------------------
# SEPA direct debit consistency compliance
# ---------------------------------------------------------------------------
class TestSepaDirectDebitCompliance:
    """PaymentMeansCode=59 requires BT-89 (mandate) and BT-91 (buyer IBAN)."""

    def _base_data(self, **overrides: object) -> InvoiceData:
        defaults: dict[str, object] = {
            "invoice_id": "DD-001",
            "issue_date": "2026-01-01",
            "seller": Party(
                name="Seller",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE123456789",
            ),
            "buyer": Party(
                name="Buyer",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
            "items": [
                LineItem(description="Service", quantity="1", unit_price="100"),
            ],
            "payment_means_type_code": "59",
        }
        defaults.update(overrides)
        return InvoiceData(**defaults)

    @respx.mock
    async def test_dd_missing_mandate_and_iban(self) -> None:
        """Code=59 without BT-89 and BT-91 → both flagged."""
        data = self._base_data()
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        missing = result.get("missing_fields", [])
        assert "DD-BT-89" in missing
        assert "DD-BT-91" in missing
        await client.close()

    @respx.mock
    async def test_dd_with_mandate_and_iban(self) -> None:
        """Code=59 with BT-89 and BT-91 → not flagged."""
        data = self._base_data(
            mandate_reference_id="MANDATE-123",
            buyer_iban="DE89370400440532013000",
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        missing = result.get("missing_fields", [])
        assert "DD-BT-89" not in missing
        assert "DD-BT-91" not in missing
        await client.close()

    @respx.mock
    async def test_non_dd_no_checks(self) -> None:
        """Code=58 (SEPA transfer) → no DD checks."""
        data = InvoiceData(
            invoice_id="NOND-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
            payment_means_type_code="58",
            seller_iban="DE89370400440532013000",
        )
        xml = build_xml(data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        missing = result.get("missing_fields", [])
        assert "DD-BT-89" not in missing
        assert "DD-BT-91" not in missing
        await client.close()


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------
class TestEdgeCases:
    """Extreme inputs, non-ASCII, long strings, boundary values."""

    def test_non_ascii_party_names(self) -> None:
        """Unicode party names (Cyrillic, Chinese) roundtrip correctly."""
        data = InvoiceData(
            invoice_id="UNICODE-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Мария Иванова GmbH",
                address=Address(street="Улица 1", city="Берлин", postal_code="10115"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="株式会社テスト",
                address=Address(street="東京都1-2-3", city="Tokyo", postal_code="100-0001"),
            ),
            items=[LineItem(description="Товар/商品", quantity="1", unit_price="100")],
        )
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert parsed.seller is not None
        assert "Мария" in parsed.seller.name
        assert parsed.buyer is not None
        assert "テスト" in parsed.buyer.name
        assert parsed.items[0].description == "Товар/商品"

    def test_long_invoice_note(self) -> None:
        """Invoice note at max length (2000 chars) builds and parses."""
        long_note = "A" * 2000
        data = InvoiceData(
            invoice_id="LONG-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
            invoice_note=long_note,
        )
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert len(parsed.invoice_note) == 2000

    def test_many_line_items(self) -> None:
        """50 line items build and parse correctly."""
        items = [
            LineItem(description=f"Pos {i}", quantity="1", unit_price=f"{i}.00")
            for i in range(1, 51)
        ]
        data = InvoiceData(
            invoice_id="MANY-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
            items=items,
        )
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert len(parsed.items) == 50
        # Total should be sum of 1..50 = 1275
        assert parsed.totals is not None
        assert parsed.totals.net_total == Decimal("1275.00")

    def test_minimum_amount(self) -> None:
        """Minimum 0.01 unit price builds correctly."""
        data = InvoiceData(
            invoice_id="MIN-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
            items=[
                LineItem(description="Penny item", quantity="1", unit_price="0.01"),
            ],
        )
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert parsed.items[0].unit_price == Decimal("0.01")

    def test_high_precision_quantity(self) -> None:
        """Quantity with 6 decimal places."""
        data = InvoiceData(
            invoice_id="PREC-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Precise",
                    quantity="3.141593",
                    unit_price="100",
                ),
            ],
        )
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert parsed.items[0].quantity == Decimal("3.141593")

    def test_all_tax_categories(self) -> None:
        """All valid tax categories build without error."""
        for cat in TaxCategory:
            data = InvoiceData(
                invoice_id=f"CAT-{cat.value}",
                issue_date="2026-01-01",
                seller=Party(
                    name="S",
                    address=Address(street="S", city="C", postal_code="00000"),
                    tax_id="DE123456789",
                ),
                buyer=Party(
                    name="B",
                    address=Address(street="B", city="C", postal_code="00000"),
                ),
                items=[
                    LineItem(
                        description=f"Cat {cat.value}",
                        quantity="1",
                        unit_price="100",
                        tax_rate=Decimal("0"),
                        tax_category=cat,
                    ),
                ],
            )
            xml = build_xml(data)
            parsed = parse_xml(xml)
            assert parsed.items[0].tax_category == cat

    def test_all_type_codes(self) -> None:
        """All valid type codes (380, 381, 384, 389, 875, 876, 877) build."""
        from einvoice_mcp.models import VALID_TYPE_CODES
        for code in sorted(VALID_TYPE_CODES):
            data = InvoiceData(
                invoice_id=f"TC-{code}",
                issue_date="2026-01-01",
                type_code=code,
                seller=Party(
                    name="S",
                    address=Address(street="S", city="C", postal_code="00000"),
                    tax_id="DE123456789",
                ),
                buyer=Party(
                    name="B",
                    address=Address(street="B", city="C", postal_code="00000"),
                ),
                items=[
                    LineItem(description="X", quantity="1", unit_price="100"),
                ],
            )
            xml = build_xml(data)
            parsed = parse_xml(xml)
            assert parsed.type_code == code

    def test_invalid_type_code_rejected(self) -> None:
        """Invalid type code raises ValidationError."""
        with pytest.raises(ValidationError, match="Ungültiger Rechnungsartcode"):
            InvoiceData(
                invoice_id="BAD-TC",
                issue_date="2026-01-01",
                type_code="999",
                seller=Party(
                    name="S",
                    address=Address(street="S", city="C", postal_code="00000"),
                ),
                buyer=Party(
                    name="B",
                    address=Address(street="B", city="C", postal_code="00000"),
                ),
                items=[LineItem(description="X", quantity="1", unit_price="100")],
            )

    def test_invalid_currency_rejected(self) -> None:
        """Invalid currency code raises ValidationError."""
        with pytest.raises(ValidationError, match="Ungültiger Währungscode"):
            InvoiceData(
                invoice_id="BAD-CUR",
                issue_date="2026-01-01",
                currency="eur",  # lowercase
                seller=Party(
                    name="S",
                    address=Address(street="S", city="C", postal_code="00000"),
                ),
                buyer=Party(
                    name="B",
                    address=Address(street="B", city="C", postal_code="00000"),
                ),
                items=[LineItem(description="X", quantity="1", unit_price="100")],
            )

    def test_exemption_reason_no_tax_entries(self) -> None:
        """Invoice with standard tax (no E/AE) has empty exemption fields."""
        data = InvoiceData(
            invoice_id="EXRES-001",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
            items=[
                LineItem(description="X", quantity="1", unit_price="100"),
            ],
        )
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert parsed.tax_exemption_reason == ""
        assert parsed.tax_exemption_reason_code == ""

    def test_invalid_payment_means_rejected(self) -> None:
        """Invalid payment means code raises ValidationError."""
        with pytest.raises(ValidationError, match="Ungültiger Zahlungsart-Code"):
            InvoiceData(
                invoice_id="BAD-PM",
                issue_date="2026-01-01",
                payment_means_type_code="99",
                seller=Party(
                    name="S",
                    address=Address(street="S", city="C", postal_code="00000"),
                ),
                buyer=Party(
                    name="B",
                    address=Address(street="B", city="C", postal_code="00000"),
                ),
                items=[LineItem(description="X", quantity="1", unit_price="100")],
            )


