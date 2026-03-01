"""KoSIT Validator HTTP client."""

import asyncio
import logging

import httpx
from defusedxml import ElementTree
from defusedxml.common import DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden

from einvoice_mcp.config import settings
from einvoice_mcp.errors import KoSITConnectionError, KoSITValidationError
from einvoice_mcp.models import ValidationError, ValidationResult

logger = logging.getLogger(__name__)

KOSIT_NS = {
    "rep": "http://www.xoev.de/de/validator/varl/1",
    "s": "http://www.xoev.de/de/validator/framework/1/scenarios",
    "svrl": "http://purl.oclc.org/dml/schematron/output/",
}


MAX_REPORT_SIZE = 512 * 1024  # 512 KB cap on raw KoSIT reports
MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10 MB hard cap on KoSIT response body


class KoSITClient:
    """Async HTTP client for the KoSIT Validator daemon."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.kosit_url).rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        async with self._lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=30.0,
                    follow_redirects=False,  # SSRF defense: prevent redirect to internal services
                    limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
                )
            return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get("/server/health")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def validate(self, xml_bytes: bytes) -> ValidationResult:
        try:
            client = await self._get_client()
            resp = await client.post(
                "/",
                content=xml_bytes,
                headers={"Content-Type": "application/xml"},
            )
        except httpx.ConnectError as exc:
            raise KoSITConnectionError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise KoSITValidationError(str(exc)) from exc

        # Guard against oversized responses from a compromised/rogue KoSIT instance
        content_length = resp.headers.get("content-length")
        try:
            if content_length and int(content_length) > MAX_RESPONSE_SIZE:
                raise KoSITValidationError(
                    "Antwort des Validators überschreitet Größenlimit.", controlled=True
                )
        except ValueError:
            pass  # Non-numeric Content-Length — fall through to body size check

        raw_report = resp.text
        if len(raw_report) > MAX_RESPONSE_SIZE:
            raise KoSITValidationError(
                "Antwort des Validators überschreitet Größenlimit.", controlled=True
            )

        if resp.status_code == 200:
            return self._parse_report(raw_report, valid=True)
        if resp.status_code == 406:
            return self._parse_report(raw_report, valid=False)
        if resp.status_code == 422:
            raise KoSITValidationError(
                "Konfigurationsfehler im Validator (HTTP 422).", controlled=True
            )
        raise KoSITValidationError(f"Unerwarteter HTTP-Status: {resp.status_code}", controlled=True)

    def _parse_report(self, raw_xml: str, *, valid: bool) -> ValidationResult:
        errors: list[ValidationError] = []
        warnings: list[ValidationError] = []
        profile = ""

        try:
            root = ElementTree.fromstring(raw_xml)

            # Extract profile from assessment
            assessment = root.find(".//rep:assessment", KOSIT_NS)
            if assessment is not None:
                profile_el = assessment.find(".//rep:profileName", KOSIT_NS)
                if profile_el is not None and profile_el.text:
                    profile = profile_el.text

            # Extract SVRL messages
            for failed in root.iter("{http://purl.oclc.org/dml/schematron/output/}failed-assert"):
                text_el = failed.find("{http://purl.oclc.org/dml/schematron/output/}text")
                message = text_el.text.strip() if text_el is not None and text_el.text else ""
                location = failed.get("location", "")
                flag = failed.get("flag", "error")

                entry = ValidationError(
                    code=failed.get("id", ""),
                    message=message,
                    severity=flag,
                    location=location,
                )
                if flag == "warning":
                    warnings.append(entry)
                else:
                    errors.append(entry)

        except (
            ElementTree.ParseError,
            EntitiesForbidden,
            DTDForbidden,
            ExternalReferenceForbidden,
        ):
            logger.warning("Could not parse KoSIT report XML, returning raw report")

        # Cap raw report to avoid bloating response payloads
        capped_report = raw_xml[:MAX_REPORT_SIZE] if len(raw_xml) > MAX_REPORT_SIZE else raw_xml

        return ValidationResult(
            valid=valid and len(errors) == 0,
            errors=errors,
            warnings=warnings,
            profile=profile,
            raw_report=capped_report,
        )
