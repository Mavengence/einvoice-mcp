"""Core InvoiceData model for invoice generation."""

import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from einvoice_mcp.models.enums import VALID_PAYMENT_MEANS_CODES, VALID_TYPE_CODES, InvoiceProfile
from einvoice_mcp.models.line_items import (
    AllowanceCharge,
    LineItem,
    SupportingDocument,
)
from einvoice_mcp.models.party import Party

# IBAN: 2-letter country code + 2 check digits + up to 30 alphanumeric BBAN
_IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
# BIC/SWIFT: 8 or 11 alphanumeric characters
_BIC_RE = re.compile(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")


class InvoiceData(BaseModel):
    invoice_id: str = Field(..., min_length=1, max_length=100, description="Rechnungsnummer")
    issue_date: date = Field(..., description="Rechnungsdatum (YYYY-MM-DD)")
    type_code: str = Field(
        default="380",
        description="Rechnungsartcode (BT-3): 380=Rechnung, 381=Gutschrift, 384=Korrekturrechnung",
    )

    @field_validator("type_code")
    @classmethod
    def validate_type_code(cls, v: str) -> str:
        if v not in VALID_TYPE_CODES:
            allowed = ", ".join(sorted(VALID_TYPE_CODES))
            raise ValueError(f"Ungültiger Rechnungsartcode '{v}'. Erlaubt: {allowed}")
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        if not v.isalpha() or not v.isupper():
            raise ValueError(
                f"Ungültiger Währungscode '{v}'. "
                "ISO 4217 in Großbuchstaben erwartet (z.B. EUR, USD, CHF)."
            )
        return v

    @field_validator("payment_means_type_code")
    @classmethod
    def validate_payment_means(cls, v: str) -> str:
        if v not in VALID_PAYMENT_MEANS_CODES:
            allowed = ", ".join(sorted(VALID_PAYMENT_MEANS_CODES))
            raise ValueError(
                f"Ungültiger Zahlungsart-Code '{v}'. Erlaubt: {allowed}"
            )
        return v

    @field_validator("seller_iban", "buyer_iban")
    @classmethod
    def validate_iban(cls, v: str | None) -> str | None:
        if v is None:
            return v
        normalized = v.replace(" ", "").upper()
        if not _IBAN_RE.match(normalized):
            raise ValueError(
                f"Ungültiges IBAN-Format '{v}'. "
                "Erwartet: 2 Buchstaben Ländercode + 2 Prüfziffern "
                "+ 11-30 alphanumerische Zeichen (z.B. DE89370400440532013000)."
            )
        return normalized

    @field_validator("seller_bic")
    @classmethod
    def validate_bic(cls, v: str | None) -> str | None:
        if v is None:
            return v
        normalized = v.replace(" ", "").upper()
        if not _BIC_RE.match(normalized):
            raise ValueError(
                f"Ungültiges BIC-Format '{v}'. "
                "Erwartet: 8 oder 11 Zeichen (z.B. COBADEFFXXX)."
            )
        return normalized

    seller: Party = Field(..., description="Verkaeufer / Rechnungssteller")
    buyer: Party = Field(..., description="Kaeufer / Rechnungsempfaenger")
    items: list[LineItem] = Field(
        ..., min_length=1, max_length=1000, description="Rechnungspositionen"
    )
    allowances_charges: list[AllowanceCharge] = Field(
        default_factory=list,
        max_length=100,
        description="Dokumentebene Zu-/Abschlaege (BG-20/BG-21)",
    )
    currency: str = Field(
        default="EUR", min_length=3, max_length=3, description="ISO 4217 Waehrungscode"
    )
    payment_terms_days: int | None = Field(
        default=None, ge=0, le=365, description="Zahlungsziel in Tagen"
    )
    leitweg_id: str | None = Field(
        default=None, max_length=100, description="Leitweg-ID (fuer oeffentliche Auftraggeber)"
    )
    buyer_reference: str | None = Field(
        default=None, max_length=100, description="Kaeuferreferenz / Bestellnummer (BT-10)"
    )
    profile: InvoiceProfile = Field(default=InvoiceProfile.XRECHNUNG, description="Rechnungsprofil")
    seller_tax_representative: Party | None = Field(
        default=None,
        description=(
            "Steuerlicher Vertreter des Verkaeufers (BG-11, BT-62..BT-65) -- "
            "Pflicht wenn Verkaeufer keinen Sitz im Steuerland hat"
        ),
    )
    seller_contact_name: str | None = Field(
        default=None,
        max_length=200,
        description="Ansprechpartner des Verkaeufers (BT-41, BR-DE-5)",
    )
    seller_contact_email: str | None = Field(
        default=None,
        max_length=200,
        description="E-Mail des Ansprechpartners (BT-43, BR-DE-7)",
    )
    seller_contact_phone: str | None = Field(
        default=None,
        max_length=50,
        description="Telefon des Ansprechpartners (BT-42)",
    )
    buyer_contact_name: str | None = Field(
        default=None,
        max_length=200,
        description="Ansprechpartner des Kaeufers (BT-44)",
    )
    buyer_contact_email: str | None = Field(
        default=None,
        max_length=200,
        description="E-Mail des Kaeufer-Ansprechpartners (BT-47)",
    )
    buyer_contact_phone: str | None = Field(
        default=None,
        max_length=50,
        description="Telefon des Kaeufer-Ansprechpartners (BT-46)",
    )
    seller_iban: str | None = Field(
        default=None,
        max_length=34,
        description="IBAN des Verkaeufers (BT-84) -- Pflicht bei SEPA-Ueberweisung",
    )
    seller_bic: str | None = Field(
        default=None,
        max_length=11,
        description="BIC der Bank des Verkaeufers (BT-86, optional)",
    )
    seller_bank_name: str | None = Field(
        default=None,
        max_length=200,
        description="Name der Bank des Verkaeufers (optional)",
    )
    delivery_party_name: str | None = Field(
        default=None,
        max_length=200,
        description="Name des Lieferorts (BT-70, z.B. 'Lager Hamburg')",
    )
    delivery_street: str | None = Field(
        default=None,
        max_length=200,
        description="Strasse des Lieferorts (BT-75)",
    )
    delivery_city: str | None = Field(
        default=None,
        max_length=100,
        description="Stadt des Lieferorts (BT-77)",
    )
    delivery_postal_code: str | None = Field(
        default=None,
        max_length=20,
        description="PLZ des Lieferorts (BT-78)",
    )
    delivery_country_code: str | None = Field(
        default=None,
        max_length=2,
        description="Land des Lieferorts (BT-80)",
    )
    delivery_date: date | None = Field(
        default=None,
        description="Lieferdatum / Leistungsdatum (BT-72, SS14 Abs. 4 Nr. 6 UStG)",
    )
    service_period_start: date | None = Field(
        default=None,
        description="Beginn des Leistungszeitraums (BT-73)",
    )
    service_period_end: date | None = Field(
        default=None,
        description="Ende des Leistungszeitraums (BT-74)",
    )
    due_date: date | None = Field(
        default=None,
        description="Faelligkeitsdatum (BT-9, z.B. 2026-02-15)",
    )
    invoice_note: str | None = Field(
        default=None,
        max_length=2000,
        description="Freitext-Bemerkung zur Rechnung (BT-22)",
    )
    payment_terms_text: str | None = Field(
        default=None,
        max_length=1000,
        description=(
            "Zahlungsbedingungen als Freitext "
            "(BT-20, z.B. '2% Skonto bei Zahlung innerhalb 10 Tagen')"
        ),
    )
    purchase_order_reference: str | None = Field(
        default=None,
        max_length=100,
        description="Bestellnummer des Kaeufers (BT-13)",
    )
    sales_order_reference: str | None = Field(
        default=None,
        max_length=100,
        description="Auftragsbestaetigung des Verkaeufers (BT-14)",
    )
    contract_reference: str | None = Field(
        default=None,
        max_length=100,
        description="Vertragsnummer (BT-12)",
    )
    project_reference: str | None = Field(
        default=None,
        max_length=100,
        description="Projektreferenz (BT-11)",
    )
    preceding_invoice_number: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "Vorherige Rechnungsnummer (BT-25) -- "
            "Pflicht bei Gutschrift (381) per SS14 Abs. 4 UStG"
        ),
    )
    preceding_invoice_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description=(
            "Datum der vorherigen Rechnung (BT-26, YYYY-MM-DD) -- "
            "empfohlen bei Gutschrift fuer Stornobuchhaltung"
        ),
    )
    despatch_advice_reference: str | None = Field(
        default=None,
        max_length=100,
        description="Lieferscheinnummer (BT-16)",
    )
    tender_or_lot_reference: str | None = Field(
        default=None,
        max_length=100,
        description="Vergabe- / Losnummer (BT-17) -- fuer oeffentliche Vergabeverfahren",
    )
    invoiced_object_identifier: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Kennung des Abrechnungsobjekts (BT-18) -- "
            "z.B. Vertragskonto, Zaehlernummer, Abonnement-ID"
        ),
    )
    business_process_type: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Geschaeftsprozesstyp (BT-23) -- "
            "z.B. 'urn:fdc:peppol.eu:2017:poacc:billing:01:1.0'"
        ),
    )
    buyer_iban: str | None = Field(
        default=None,
        max_length=34,
        description=(
            "IBAN des Kaeufers (BT-91) -- "
            "Pflicht bei SEPA-Lastschrift (PaymentMeansCode 59)"
        ),
    )
    mandate_reference_id: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "SEPA-Mandatsreferenz (BT-89) -- "
            "Pflicht bei SEPA-Lastschrift"
        ),
    )
    tax_exemption_reason: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Befreiungsgrund Text (BT-120) -- z.B. "
            "'Gemaess SS19 UStG wird keine Umsatzsteuer berechnet.'"
        ),
    )
    tax_exemption_reason_code: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "Befreiungsgrund Code (BT-121) -- "
            "z.B. 'vatex-eu-132' (MwStSystRL Art. 132)"
        ),
    )
    skonto_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "Skonto-Prozentsatz (z.B. 2.00 fuer 2%) -- "
            "wird automatisch in BT-20 Zahlungsbedingungen uebernommen"
        ),
    )
    skonto_days: int | None = Field(
        default=None,
        ge=0,
        le=365,
        description="Skonto-Frist in Tagen (z.B. 10 fuer '10 Tage 2% Skonto')",
    )
    skonto_base_amount: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Skonto-Basisbetrag -- "
            "falls abweichend vom Rechnungsbetrag (BT-115)"
        ),
    )
    payee_name: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Zahlungsempfaenger Name (BT-59) -- "
            "falls abweichend vom Verkaeufer (z.B. Factoring)"
        ),
    )
    payee_id: str | None = Field(
        default=None,
        max_length=100,
        description="Kennung des Zahlungsempfaengers (BT-60)",
    )
    payee_legal_registration_id: str | None = Field(
        default=None,
        max_length=100,
        description="Handelsregisternummer des Zahlungsempfaengers (BT-61)",
    )
    payment_card_pan: str | None = Field(
        default=None,
        max_length=20,
        description=(
            "Zahlungskarten-PAN -- letzte 4-6 Stellen (BT-87), "
            "z.B. '1234' fuer Kreditkartenzahlung"
        ),
    )
    payment_card_holder: str | None = Field(
        default=None,
        max_length=200,
        description="Name des Karteninhabers (BT-88)",
    )
    payment_means_type_code: str = Field(
        default="58",
        max_length=3,
        description=(
            "Zahlungsart (BT-81): "
            "58=SEPA-Ueberweisung, 30=Ueberweisung, "
            "48=Kreditkarte, 59=SEPA-Lastschrift"
        ),
    )
    remittance_information: str | None = Field(
        default=None,
        max_length=140,
        description=(
            "Verwendungszweck (BT-83) -- "
            "SEPA-Referenz fuer die Zahlungszuordnung"
        ),
    )
    receiving_advice_reference: str | None = Field(
        default=None,
        max_length=100,
        description="Wareneingangsreferenz (BT-15)",
    )
    delivery_location_id: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "Kennung des Lieferorts -- "
            "z.B. Lagerort-ID, GLN des Lieferstandorts"
        ),
    )
    payment_means_text: str | None = Field(
        default=None,
        max_length=500,
        description="Zahlungsart Freitext (BT-82, z.B. 'SEPA-Ueberweisung')",
    )
    supporting_documents: list[SupportingDocument] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "Zusaetzliche Belegdokumente (BG-24, BT-122..BT-125) -- "
            "z.B. Zollpapiere, Zertifikate, Zeitnachweise"
        ),
    )
    prepaid_amount: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Bereits gezahlter Betrag (BT-113) -- "
            "z.B. Abschlagszahlungen bei Schlussrechnungen"
        ),
    )

    @staticmethod
    def _line_net_amount(item: LineItem) -> Decimal:
        """Compute BT-131 per EN 16931: (qty * price) - allowances + charges."""
        base = (item.quantity * item.unit_price).quantize(Decimal("0.01"))
        for lac in item.allowances_charges:
            if lac.charge:
                base += lac.amount
            else:
                base -= lac.amount
        return base

    def total_net(self) -> Decimal:
        """Sum of line item net amounts (BT-106)."""
        return sum(
            (self._line_net_amount(item) for item in self.items),
            Decimal("0"),
        )

    def total_allowances(self) -> Decimal:
        """Sum of document-level allowances (BT-107)."""
        return sum(
            (ac.amount for ac in self.allowances_charges if not ac.charge),
            Decimal("0"),
        )

    def total_charges(self) -> Decimal:
        """Sum of document-level charges (BT-108)."""
        return sum(
            (ac.amount for ac in self.allowances_charges if ac.charge),
            Decimal("0"),
        )

    def tax_basis(self) -> Decimal:
        """Tax basis = line total - allowances + charges (BT-109)."""
        return (
            self.total_net() - self.total_allowances() + self.total_charges()
        ).quantize(Decimal("0.01"))

    def total_tax(self) -> Decimal:
        """Calculate tax total using per-group rounding (EN 16931 / BR-CO-14).

        Items are grouped by (tax_category, tax_rate), the net basis per group
        is summed, then tax is calculated and rounded once per group.
        Document-level allowances/charges are included in the tax groups.
        """
        tax_groups: dict[tuple[str, Decimal], Decimal] = {}
        for item in self.items:
            key = (item.tax_category.value, item.tax_rate)
            net = self._line_net_amount(item)
            tax_groups[key] = tax_groups.get(key, Decimal("0")) + net
        for ac in self.allowances_charges:
            key = (ac.tax_category.value, ac.tax_rate)
            if ac.charge:
                tax_groups[key] = tax_groups.get(key, Decimal("0")) + ac.amount
            else:
                tax_groups[key] = tax_groups.get(key, Decimal("0")) - ac.amount
        return sum(
            (
                (basis * rate / Decimal("100")).quantize(Decimal("0.01"))
                for (_, rate), basis in tax_groups.items()
            ),
            Decimal("0"),
        )

    def total_gross(self) -> Decimal:
        """Grand total = tax basis + tax total (BT-112)."""
        return (self.tax_basis() + self.total_tax()).quantize(Decimal("0.01"))
