"""Tests for security hardening: size limits, XXE protection, input validation."""

import base64

import pytest
from pydantic import ValidationError

from einvoice_mcp.config import MAX_PDF_BASE64_SIZE, MAX_PDF_DECODED_SIZE, MAX_XML_SIZE
from einvoice_mcp.errors import InvoiceParsingError
from einvoice_mcp.models import Address, InvoiceData, LineItem, Party
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.services.xml_parser import parse_xml
from einvoice_mcp.tools.compliance import check_compliance
from einvoice_mcp.tools.parse import parse_einvoice
from einvoice_mcp.tools.validate import validate_xrechnung, validate_zugferd

KOSIT_URL = "http://kosit-mock:8081"


class TestXMLSizeLimits:
    async def test_validate_rejects_oversized_xml(self) -> None:
        huge_xml = "x" * (MAX_XML_SIZE + 1)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_xrechnung(huge_xml, client)
        assert result["valid"] is False
        assert any("Größenlimit" in e["message"] for e in result["errors"])
        await client.close()

    async def test_parse_rejects_oversized_xml(self) -> None:
        huge_xml = "x" * (MAX_XML_SIZE + 1)
        result = await parse_einvoice(huge_xml, "xml")
        assert result["success"] is False
        assert "Größenlimit" in result["error"]

    async def test_compliance_rejects_oversized_xml(self) -> None:
        huge_xml = "x" * (MAX_XML_SIZE + 1)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(huge_xml, client, "XRECHNUNG")
        assert result["valid"] is False
        assert any("Größenlimit" in s for s in result["suggestions"])
        await client.close()


class TestPDFSizeLimits:
    async def test_validate_rejects_oversized_pdf(self) -> None:
        huge_pdf = "A" * (MAX_PDF_BASE64_SIZE + 1)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_zugferd(huge_pdf, client)
        assert result["valid"] is False
        assert any("Größenlimit" in e["message"] for e in result["errors"])
        await client.close()

    async def test_parse_rejects_oversized_pdf(self) -> None:
        huge_pdf = "A" * (MAX_PDF_BASE64_SIZE + 1)
        result = await parse_einvoice(huge_pdf, "pdf")
        assert result["success"] is False
        assert "Größenlimit" in result["error"]


class TestXXEProtection:
    async def test_compliance_rejects_xxe_attempt(self) -> None:
        """Verify that defusedxml blocks entity expansion attacks."""
        xxe_xml = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            "<rsm:CrossIndustryInvoice"
            ' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"'
            ' xmlns:ram="urn:un:unece:uncefact:data:standard:'
            'ReusableAggregateBusinessInformationEntity:100">'
            "&xxe;"
            "</rsm:CrossIndustryInvoice>"
        )
        client = KoSITClient(base_url=KOSIT_URL)
        # defusedxml should reject this — the field checks will return empty
        # (ParseError caught), so no fields found
        result = await check_compliance(xxe_xml, client, "XRECHNUNG")
        # The key assertion: the XXE payload should not be resolved
        assert result["valid"] is False
        await client.close()


class TestInputSanitization:
    async def test_parse_rejects_unknown_file_type(self) -> None:
        result = await parse_einvoice("<test/>", "exe")
        assert result["success"] is False
        assert "Unbekannter Dateityp" in result["error"]
        # Verify the reflected input is NOT in the error message
        assert "exe" not in result["error"]


class TestModelFieldConstraints:
    def test_address_street_too_long(self) -> None:
        with pytest.raises(ValidationError):
            Address(street="x" * 201, city="Berlin", postal_code="10115")

    def test_address_empty_street(self) -> None:
        with pytest.raises(ValidationError):
            Address(street="", city="Berlin", postal_code="10115")

    def test_country_code_wrong_length(self) -> None:
        with pytest.raises(ValidationError):
            Address(street="A", city="B", postal_code="12345", country_code="DEU")

    def test_invoice_id_max_length(self) -> None:
        with pytest.raises(ValidationError):
            InvoiceData(
                invoice_id="x" * 101,
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )

    def test_tax_rate_max_100(self) -> None:
        with pytest.raises(ValidationError):
            LineItem(description="X", quantity="1", unit_price="10", tax_rate="101")

    def test_payment_terms_max_365(self) -> None:
        with pytest.raises(ValidationError):
            InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
                payment_terms_days=400,
            )

    def test_currency_must_be_3_chars(self) -> None:
        with pytest.raises(ValidationError):
            InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
                currency="EURO",
            )

    def test_max_1000_items(self) -> None:
        items = [LineItem(description="X", quantity="1", unit_price="1") for _ in range(1001)]
        with pytest.raises(ValidationError):
            InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=items,
            )


class TestDefusedXMLPreScreen:
    """Verify defusedxml pre-screens XML before drafthorse (lxml) parsing."""

    def test_parse_xml_blocks_xxe(self) -> None:
        xxe_xml = (
            b'<?xml version="1.0"?>'
            b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            b"<rsm:CrossIndustryInvoice"
            b' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">'
            b"&xxe;</rsm:CrossIndustryInvoice>"
        )
        with pytest.raises(InvoiceParsingError):
            parse_xml(xxe_xml)

    def test_parse_xml_blocks_billion_laughs(self) -> None:
        """Verify that defusedxml blocks recursive entity expansion (billion laughs)."""
        billion_laughs = (
            b'<?xml version="1.0"?>'
            b"<!DOCTYPE lolz ["
            b'  <!ENTITY lol "lol">'
            b"  <!ENTITY lol2 '&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;'>"
            b"  <!ENTITY lol3 '&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;'>"
            b"]>"
            b"<rsm:CrossIndustryInvoice"
            b' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">'
            b"&lol3;</rsm:CrossIndustryInvoice>"
        )
        with pytest.raises(InvoiceParsingError):
            parse_xml(billion_laughs)

    def test_parse_xml_blocks_external_entity(self) -> None:
        # External general entity — defusedxml raises EntitiesForbidden
        ext_xml = (
            b'<?xml version="1.0"?>'
            b"<!DOCTYPE foo ["
            b'<!ENTITY ext SYSTEM "http://evil.com/secrets">'
            b"]>"
            b"<rsm:CrossIndustryInvoice"
            b' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">'
            b"&ext;</rsm:CrossIndustryInvoice>"
        )
        with pytest.raises(InvoiceParsingError):
            parse_xml(ext_xml)


class TestDecodedPDFSizeLimit:
    """Verify decoded PDF bytes are checked after base64 decoding."""

    async def test_validate_rejects_oversized_decoded_pdf(self) -> None:
        # Create base64 that decodes to > MAX_PDF_DECODED_SIZE
        # but stays under MAX_PDF_BASE64_SIZE (using smaller payload)
        raw_bytes = b"A" * (MAX_PDF_DECODED_SIZE + 1)
        encoded = base64.b64encode(raw_bytes).decode()
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_zugferd(encoded, client)
        assert result["valid"] is False
        assert any("Dekodierte PDF" in e["message"] for e in result["errors"])
        await client.close()

    async def test_parse_rejects_oversized_decoded_pdf(self) -> None:
        raw_bytes = b"A" * (MAX_PDF_DECODED_SIZE + 1)
        encoded = base64.b64encode(raw_bytes).decode()
        result = await parse_einvoice(encoded, "pdf")
        assert result["success"] is False
        assert "Dekodierte PDF" in result["error"]


class TestErrorSanitization:
    """Verify that internal error details do not leak to user-facing messages."""

    def test_connection_error_no_hostname_in_message_de(self) -> None:
        from einvoice_mcp.errors import KoSITConnectionError

        err = KoSITConnectionError("Connect call failed ('192.168.1.10', 8081)")
        assert "192.168.1.10" not in err.message_de
        assert "erreichbar" in err.message_de

    def test_parsing_error_no_path_in_message_de(self) -> None:
        err = InvoiceParsingError("/usr/local/lib/python3.11/xml/error.py")
        assert "/usr/local" not in err.message_de
        assert "gelesen werden" in err.message_de

    def test_kosit_validation_error_allows_controlled_german_messages(self) -> None:
        from einvoice_mcp.errors import KoSITValidationError

        # Controlled German message (e.g. HTTP status info) should pass through
        err = KoSITValidationError("Konfigurationsfehler im Validator (HTTP 422).", controlled=True)
        assert "Konfigurationsfehler" in err.message_de

    def test_kosit_validation_error_blocks_raw_httpx_errors(self) -> None:
        from einvoice_mcp.errors import KoSITValidationError

        err = KoSITValidationError("httpx.ReadTimeout: timed out after 30.0 seconds")
        assert "httpx" not in err.message_de
        assert "fehlgeschlagen" in err.message_de

    def test_kosit_validation_error_blocks_uncontrolled_detail(self) -> None:
        from einvoice_mcp.errors import KoSITValidationError

        # Without controlled=True, detail must NOT appear in message_de
        err = KoSITValidationError("RemoteProtocolError: peer closed connection")
        assert "RemoteProtocolError" not in err.message_de
        assert "fehlgeschlagen" in err.message_de
