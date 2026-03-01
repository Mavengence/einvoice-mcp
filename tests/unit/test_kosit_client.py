"""Unit tests for KoSIT client with mocked HTTP."""

import httpx
import pytest
import respx

from einvoice_mcp.errors import KoSITConnectionError, KoSITValidationError
from einvoice_mcp.services.kosit import KoSITClient

MOCK_VALID_REPORT = """\
<?xml version="1.0" encoding="UTF-8"?>
<rep:report xmlns:rep="http://www.xoev.de/de/validator/varl/1"
            xmlns:s="http://www.xoev.de/de/validator/framework/1/scenarios">
  <rep:assessment>
    <rep:profileName>XRechnung 3.0.2</rep:profileName>
  </rep:assessment>
</rep:report>
"""

MOCK_INVALID_REPORT = """\
<?xml version="1.0" encoding="UTF-8"?>
<rep:report xmlns:rep="http://www.xoev.de/de/validator/varl/1"
            xmlns:svrl="http://purl.oclc.org/dml/schematron/output/">
  <svrl:schematron-output>
    <svrl:failed-assert id="BR-01" location="/Invoice" flag="error">
      <svrl:text>BT-1 (Invoice number) is mandatory.</svrl:text>
    </svrl:failed-assert>
    <svrl:failed-assert id="BR-W-01" location="/Invoice" flag="warning">
      <svrl:text>Consider adding payment terms.</svrl:text>
    </svrl:failed-assert>
  </svrl:schematron-output>
</rep:report>
"""

BASE_URL = "http://kosit-test:8081"


@pytest.fixture
def client() -> KoSITClient:
    return KoSITClient(base_url=BASE_URL)


class TestHealthCheck:
    @respx.mock
    async def test_healthy(self, client: KoSITClient) -> None:
        respx.get(f"{BASE_URL}/server/health").respond(200)
        assert await client.health_check() is True
        await client.close()

    @respx.mock
    async def test_unhealthy(self, client: KoSITClient) -> None:
        respx.get(f"{BASE_URL}/server/health").respond(500)
        assert await client.health_check() is False
        await client.close()

    @respx.mock
    async def test_connection_error(self, client: KoSITClient) -> None:
        respx.get(f"{BASE_URL}/server/health").mock(side_effect=httpx.ConnectError("refused"))
        assert await client.health_check() is False
        await client.close()


class TestValidate:
    @respx.mock
    async def test_valid_document(self, client: KoSITClient) -> None:
        respx.post(f"{BASE_URL}/").respond(200, text=MOCK_VALID_REPORT)
        result = await client.validate(b"<Invoice/>")
        assert result.valid is True
        assert result.profile == "XRechnung 3.0.2"
        assert len(result.errors) == 0
        await client.close()

    @respx.mock
    async def test_invalid_document(self, client: KoSITClient) -> None:
        respx.post(f"{BASE_URL}/").respond(406, text=MOCK_INVALID_REPORT)
        result = await client.validate(b"<Invoice/>")
        assert result.valid is False
        assert len(result.errors) == 1
        assert "BT-1" in result.errors[0].message
        assert len(result.warnings) == 1
        await client.close()

    @respx.mock
    async def test_config_error_422(self, client: KoSITClient) -> None:
        respx.post(f"{BASE_URL}/").respond(422, text="config error")
        with pytest.raises(KoSITValidationError):
            await client.validate(b"<Invoice/>")
        await client.close()

    @respx.mock
    async def test_server_error_500(self, client: KoSITClient) -> None:
        respx.post(f"{BASE_URL}/").respond(500, text="server error")
        with pytest.raises(KoSITValidationError):
            await client.validate(b"<Invoice/>")
        await client.close()

    @respx.mock
    async def test_connection_refused(self, client: KoSITClient) -> None:
        respx.post(f"{BASE_URL}/").mock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(KoSITConnectionError):
            await client.validate(b"<Invoice/>")
        await client.close()
