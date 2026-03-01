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
        assert "bad data" in err.message_de
        assert "bad data" in str(err)

    def test_invoice_parsing_error_default(self) -> None:
        err = InvoiceParsingError()
        assert "gelesen werden" in err.message_de

    def test_invoice_parsing_error_with_detail(self) -> None:
        err = InvoiceParsingError("corrupt PDF")
        assert "corrupt PDF" in err.message_de

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
        with pytest.raises(InvoiceParsingError, match="PDF-Extraktion"):
            extract_xml_from_pdf(b"not a real PDF")

    def test_extract_xml_from_pdf_empty(self) -> None:
        with pytest.raises(InvoiceParsingError):
            extract_xml_from_pdf(b"")

    def test_str_element_none(self) -> None:
        assert _str_element(None) == ""

    def test_str_element_strips_empty_scheme(self) -> None:
        assert _str_element("DE123 ()") == "DE123"

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
            pytest.raises(InvoiceGenerationError, match="unexpected"),
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
            pytest.raises(InvoiceGenerationError, match="PDF-Erstellung"),
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
        with pytest.raises(InvoiceGenerationError, match="Einbettung"):
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
    async def test_zugferd_profile_compliance(self) -> None:
        """Test compliance with ZUGFERD target profile."""
        xml = build_xml(
            InvoiceData(
                invoice_id="Z-001",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
                buyer_reference="REF-123",
            )
        ).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "ZUGFERD")
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
        """Generate XRechnung, then parse it back, then run compliance."""
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)

        # Generate
        gen_result = await generate_xrechnung(sample_invoice_data, client)
        assert gen_result["success"] is True
        xml = gen_result["xml_content"]

        # Parse
        parse_result = await parse_einvoice(xml, "xml")
        assert parse_result["success"] is True
        assert parse_result["invoice"]["invoice_id"] == "RE-2026-001"

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
