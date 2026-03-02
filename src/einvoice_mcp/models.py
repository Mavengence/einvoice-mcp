"""Pydantic models for invoice data, validation results, and parsed output."""

import re
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

# IBAN: 2-letter country code + 2 check digits + up to 30 alphanumeric BBAN
_IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
# BIC/SWIFT: 8 or 11 alphanumeric characters
_BIC_RE = re.compile(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$")


class InvoiceProfile(StrEnum):
    XRECHNUNG = "XRECHNUNG"
    ZUGFERD_EN16931 = "ZUGFERD_EN16931"
    ZUGFERD_BASIC = "ZUGFERD_BASIC"
    ZUGFERD_EXTENDED = "ZUGFERD_EXTENDED"


class TaxCategory(StrEnum):
    S = "S"  # Standard rate
    Z = "Z"  # Zero rated
    E = "E"  # Exempt
    AE = "AE"  # Reverse charge
    K = "K"  # Intra-community supply
    G = "G"  # Export outside EU
    O = "O"  # Not subject to VAT  # noqa: E741
    L = "L"  # Canary Islands
    M = "M"  # Ceuta and Melilla


class Address(BaseModel):
    street: str = Field(..., min_length=1, max_length=200, description="Straße und Hausnummer")
    street_2: str | None = Field(
        default=None, max_length=200, description="Adresszeile 2 (BT-36/BT-51)"
    )
    street_3: str | None = Field(
        default=None, max_length=200, description="Adresszeile 3 (BT-37/BT-52)"
    )
    city: str = Field(..., min_length=1, max_length=100, description="Stadt")
    postal_code: str = Field(..., min_length=1, max_length=20, description="Postleitzahl")
    country_code: str = Field(
        default="DE", min_length=2, max_length=2, description="ISO 3166-1 alpha-2 Ländercode"
    )
    country_subdivision: str | None = Field(
        default=None,
        max_length=100,
        description="Bundesland / Region (BT-39/BT-54, z.B. 'BY' für Bayern)",
    )

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        if not v.isalpha() or not v.isupper():
            raise ValueError(
                f"Ungültiger Ländercode '{v}'. "
                "ISO 3166-1 alpha-2 erwartet (z.B. DE, AT, CH)."
            )
        return v


class Party(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Vollständiger Name")
    trading_name: str | None = Field(
        default=None,
        max_length=200,
        description="Handelsname (BT-28/BT-45) — falls abweichend vom rechtlichen Namen",
    )
    address: Address
    tax_id: str | None = Field(
        default=None, max_length=30, description="USt-IdNr. (BT-31, z.B. DE123456789)"
    )
    tax_number: str | None = Field(
        default=None,
        max_length=30,
        description="Steuernummer (BT-32, z.B. 123/456/78901) — alternativ zu USt-IdNr.",
    )
    registration_id: str | None = Field(
        default=None, max_length=50, description="Handelsregisternummer oder GLN"
    )
    electronic_address: str | None = Field(
        default=None,
        max_length=200,
        description="Elektronische Adresse (BT-34/BT-49), z.B. E-Mail oder Peppol-ID",
    )
    electronic_address_scheme: str = Field(
        default="EM",
        max_length=10,
        description="EAS-Code für elektronische Adresse (EM=E-Mail, 9930=USt-IdNr.)",
    )
    contact_name: str | None = Field(
        default=None, max_length=200, description="Ansprechpartner (BT-41)"
    )
    contact_phone: str | None = Field(
        default=None, max_length=50, description="Telefon des Ansprechpartners (BT-42)"
    )
    contact_email: str | None = Field(
        default=None, max_length=200, description="E-Mail des Ansprechpartners (BT-43)"
    )


class ItemAttribute(BaseModel):
    """Item attribute name/value pair (BG-30, BT-160/BT-161).

    Used for product characteristics like color, size, batch codes.
    """

    name: str = Field(
        ..., min_length=1, max_length=200,
        description="Attributname (BT-160, z.B. 'Farbe', 'Größe')",
    )
    value: str = Field(
        ..., min_length=1, max_length=500,
        description="Attributwert (BT-161, z.B. 'Rot', 'XL')",
    )


class LineAllowanceCharge(BaseModel):
    """Line-level allowance or charge (BG-27/BG-28).

    charge=False → line allowance/discount (BT-136..BT-139)
    charge=True  → line charge/surcharge (BT-141..BT-144)
    """

    charge: bool = Field(
        default=False,
        description="True=Zuschlag, False=Abzug/Rabatt",
    )
    amount: Decimal = Field(
        ..., ge=0, description="Betrag (BT-136/BT-141)"
    )
    reason: str = Field(
        default="", max_length=500, description="Grund (BT-139/BT-144)"
    )


class LineItem(BaseModel):
    description: str = Field(..., min_length=1, max_length=500, description="Positionsbeschreibung")
    quantity: Decimal = Field(..., gt=0, description="Menge")
    unit_code: str = Field(
        default="H87", max_length=10, description="UN/ECE Einheitencode (H87=Stück, HUR=Stunde)"
    )
    unit_price: Decimal = Field(..., ge=0, description="Netto-Einzelpreis in EUR")
    tax_rate: Decimal = Field(default=Decimal("19.00"), ge=0, le=100, description="Steuersatz in %")
    tax_category: TaxCategory = Field(default=TaxCategory.S, description="Steuerkategorie")
    seller_item_id: str | None = Field(
        default=None, max_length=100, description="Artikelnummer des Verkäufers (BT-155)"
    )
    buyer_item_id: str | None = Field(
        default=None, max_length=100, description="Artikelnummer des Käufers (BT-156)"
    )
    standard_item_id: str | None = Field(
        default=None, max_length=100, description="Standard-Artikelnummer GTIN/EAN (BT-157)"
    )
    standard_item_scheme: str = Field(
        default="0160", max_length=10, description="Schema der Standard-Artikelnr. (0160=GTIN)"
    )
    item_note: str | None = Field(
        default=None, max_length=1000, description="Positionshinweis (BT-127)"
    )
    item_gross_price: Decimal | None = Field(
        default=None,
        ge=0,
        description="Brutto-Einzelpreis (BT-148) — vor Abzug von Rabatten",
    )
    item_price_discount: Decimal | None = Field(
        default=None,
        ge=0,
        description="Preisabschlag pro Einheit (BT-147) — Brutto-/Netto-Differenz",
    )
    item_classification_id: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "Klassifizierungscode (BT-158) — "
            "z.B. CPV-Code für öffentliche Vergabe"
        ),
    )
    item_classification_scheme: str = Field(
        default="STL",
        max_length=20,
        description="Schema der Klassifizierung (BT-158-1, z.B. STL, CPV)",
    )
    item_classification_version: str = Field(
        default="",
        max_length=50,
        description="Version des Klassifizierungsschemas (BT-158-2, z.B. '2008')",
    )
    allowances_charges: list["LineAllowanceCharge"] = Field(
        default_factory=list,
        max_length=50,
        description="Positions-Zu-/Abschläge (BG-27/BG-28)",
    )
    buyer_accounting_reference: str | None = Field(
        default=None,
        max_length=200,
        description="Kontierungsreferenz des Käufers (BT-133)",
    )
    line_period_start: date | None = Field(
        default=None,
        description="Abrechnungszeitraum Beginn (BT-134) — für wiederkehrende Leistungen",
    )
    line_period_end: date | None = Field(
        default=None,
        description="Abrechnungszeitraum Ende (BT-135) — für wiederkehrende Leistungen",
    )
    item_country_of_origin: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Ursprungsland des Artikels (BT-159, ISO 3166-1 alpha-2)",
    )
    attributes: list["ItemAttribute"] = Field(
        default_factory=list,
        max_length=50,
        description="Artikelmerkmale (BG-30, BT-160/BT-161) — Name/Wert-Paare",
    )


class AllowanceCharge(BaseModel):
    """Document-level allowance or charge (BG-20/BG-21).

    charge=False → allowance/discount (BT-92..BT-99)
    charge=True  → surcharge/charge (BT-99..BT-105)
    """

    charge: bool = Field(
        default=False,
        description="True=Zuschlag, False=Abzug/Rabatt",
    )
    amount: Decimal = Field(
        ..., ge=0, description="Betrag (BT-92/BT-99)"
    )
    reason: str = Field(
        default="", max_length=500, description="Grund (BT-97/BT-104)"
    )
    reason_code: str = Field(
        default="", max_length=10, description="Grundcode (BT-98/BT-105)"
    )
    tax_rate: Decimal = Field(
        default=Decimal("19.00"), ge=0, le=100, description="Steuersatz in %"
    )
    tax_category: TaxCategory = Field(
        default=TaxCategory.S, description="Steuerkategorie"
    )
    base_amount: Decimal | None = Field(
        default=None, ge=0, description="Basisbetrag für Prozentberechnung (BT-93/BT-100)"
    )
    percentage: Decimal | None = Field(
        default=None, ge=0, le=100, description="Prozentsatz (BT-94/BT-101)"
    )


class SupportingDocument(BaseModel):
    """Additional supporting document (BG-24, BT-122..BT-125).

    Attach invoices, customs documents, certificates, or other files.
    """

    id: str = Field(
        ..., min_length=1, max_length=200,
        description="Dokumentenreferenz (BT-122)",
    )
    description: str = Field(
        default="",
        max_length=500,
        description="Beschreibung des Dokuments (BT-123)",
    )
    uri: str | None = Field(
        default=None,
        max_length=2000,
        description="Externer Speicherort / URI (BT-124)",
    )
    mime_type: str = Field(
        default="application/pdf",
        max_length=100,
        description="MIME-Typ des Anhangs (z.B. application/pdf)",
    )
    filename: str = Field(
        default="",
        max_length=200,
        description="Dateiname des Anhangs",
    )
    content_base64: str | None = Field(
        default=None,
        description="Anhang als Base64-kodierter Inhalt (BT-125)",
    )


# Valid EN 16931 invoice type codes
VALID_TYPE_CODES = frozenset({"380", "381", "384", "389", "875", "876", "877"})

# UN/CEFACT UNTDID 4461 payment means codes used in EN 16931
VALID_PAYMENT_MEANS_CODES = frozenset({
    "1", "10", "20", "30", "31", "42", "48", "49", "57", "58", "59", "97",
    "ZZZ",  # Mutually defined
})


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

    seller: Party = Field(..., description="Verkäufer / Rechnungssteller")
    buyer: Party = Field(..., description="Käufer / Rechnungsempfänger")
    items: list[LineItem] = Field(
        ..., min_length=1, max_length=1000, description="Rechnungspositionen"
    )
    allowances_charges: list[AllowanceCharge] = Field(
        default_factory=list,
        max_length=100,
        description="Dokumentebene Zu-/Abschläge (BG-20/BG-21)",
    )
    currency: str = Field(
        default="EUR", min_length=3, max_length=3, description="ISO 4217 Währungscode"
    )
    payment_terms_days: int | None = Field(
        default=None, ge=0, le=365, description="Zahlungsziel in Tagen"
    )
    leitweg_id: str | None = Field(
        default=None, max_length=100, description="Leitweg-ID (für öffentliche Auftraggeber)"
    )
    buyer_reference: str | None = Field(
        default=None, max_length=100, description="Käuferreferenz / Bestellnummer (BT-10)"
    )
    profile: InvoiceProfile = Field(default=InvoiceProfile.XRECHNUNG, description="Rechnungsprofil")
    seller_tax_representative: Party | None = Field(
        default=None,
        description=(
            "Steuerlicher Vertreter des Verkäufers (BG-11, BT-62..BT-65) — "
            "Pflicht wenn Verkäufer keinen Sitz im Steuerland hat"
        ),
    )
    seller_contact_name: str | None = Field(
        default=None,
        max_length=200,
        description="Ansprechpartner des Verkäufers (BT-41, BR-DE-5)",
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
        description="Ansprechpartner des Käufers (BT-44)",
    )
    buyer_contact_email: str | None = Field(
        default=None,
        max_length=200,
        description="E-Mail des Käufer-Ansprechpartners (BT-47)",
    )
    buyer_contact_phone: str | None = Field(
        default=None,
        max_length=50,
        description="Telefon des Käufer-Ansprechpartners (BT-46)",
    )
    seller_iban: str | None = Field(
        default=None,
        max_length=34,
        description="IBAN des Verkäufers (BT-84) — Pflicht bei SEPA-Überweisung",
    )
    seller_bic: str | None = Field(
        default=None,
        max_length=11,
        description="BIC der Bank des Verkäufers (BT-86, optional)",
    )
    seller_bank_name: str | None = Field(
        default=None,
        max_length=200,
        description="Name der Bank des Verkäufers (optional)",
    )
    delivery_party_name: str | None = Field(
        default=None,
        max_length=200,
        description="Name des Lieferorts (BT-70, z.B. 'Lager Hamburg')",
    )
    delivery_street: str | None = Field(
        default=None,
        max_length=200,
        description="Straße des Lieferorts (BT-75)",
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
        description="Lieferdatum / Leistungsdatum (BT-71, §14 Abs. 4 Nr. 6 UStG)",
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
        description="Fälligkeitsdatum (BT-9, z.B. 2026-02-15)",
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
        description="Bestellnummer des Käufers (BT-13)",
    )
    sales_order_reference: str | None = Field(
        default=None,
        max_length=100,
        description="Auftragsbestätigung des Verkäufers (BT-14)",
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
            "Vorherige Rechnungsnummer (BT-25) — "
            "Pflicht bei Gutschrift (381) per §14 Abs. 4 UStG"
        ),
    )
    preceding_invoice_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description=(
            "Datum der vorherigen Rechnung (BT-26, YYYY-MM-DD) — "
            "empfohlen bei Gutschrift für Stornobuchhaltung"
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
        description="Vergabe- / Losnummer (BT-17) — für öffentliche Vergabeverfahren",
    )
    invoiced_object_identifier: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Kennung des Abrechnungsobjekts (BT-18) — "
            "z.B. Vertragskonto, Zählernummer, Abonnement-ID"
        ),
    )
    business_process_type: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Geschäftsprozesstyp (BT-23) — "
            "z.B. 'urn:fdc:peppol.eu:2017:poacc:billing:01:1.0'"
        ),
    )
    buyer_iban: str | None = Field(
        default=None,
        max_length=34,
        description=(
            "IBAN des Käufers (BT-91) — "
            "Pflicht bei SEPA-Lastschrift (PaymentMeansCode 59)"
        ),
    )
    mandate_reference_id: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "SEPA-Mandatsreferenz (BT-89) — "
            "Pflicht bei SEPA-Lastschrift"
        ),
    )
    tax_exemption_reason: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Befreiungsgrund Text (BT-120) — z.B. "
            "'Gemäß §19 UStG wird keine Umsatzsteuer berechnet.'"
        ),
    )
    tax_exemption_reason_code: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "Befreiungsgrund Code (BT-121) — "
            "z.B. 'vatex-eu-132' (MwStSystRL Art. 132)"
        ),
    )
    skonto_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "Skonto-Prozentsatz (z.B. 2.00 für 2%) — "
            "wird automatisch in BT-20 Zahlungsbedingungen übernommen"
        ),
    )
    skonto_days: int | None = Field(
        default=None,
        ge=0,
        le=365,
        description="Skonto-Frist in Tagen (z.B. 10 für '10 Tage 2% Skonto')",
    )
    skonto_base_amount: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Skonto-Basisbetrag — "
            "falls abweichend vom Rechnungsbetrag (BT-115)"
        ),
    )
    payee_name: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Zahlungsempfänger Name (BT-59) — "
            "falls abweichend vom Verkäufer (z.B. Factoring)"
        ),
    )
    payee_id: str | None = Field(
        default=None,
        max_length=100,
        description="Kennung des Zahlungsempfängers (BT-60)",
    )
    payee_legal_registration_id: str | None = Field(
        default=None,
        max_length=100,
        description="Handelsregisternummer des Zahlungsempfängers (BT-61)",
    )
    payment_card_pan: str | None = Field(
        default=None,
        max_length=20,
        description=(
            "Zahlungskarten-PAN — letzte 4-6 Stellen (BT-87), "
            "z.B. '1234' für Kreditkartenzahlung"
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
            "58=SEPA-Überweisung, 30=Überweisung, "
            "48=Kreditkarte, 59=SEPA-Lastschrift"
        ),
    )
    remittance_information: str | None = Field(
        default=None,
        max_length=140,
        description=(
            "Verwendungszweck (BT-83) — "
            "SEPA-Referenz für die Zahlungszuordnung"
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
            "Kennung des Lieferorts (BT-71) — "
            "z.B. Lagerort-ID, GLN des Lieferstandorts"
        ),
    )
    payment_means_text: str | None = Field(
        default=None,
        max_length=500,
        description="Zahlungsart Freitext (BT-82, z.B. 'SEPA-Überweisung')",
    )
    supporting_documents: list["SupportingDocument"] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "Zusätzliche Belegdokumente (BG-24, BT-122..BT-125) — "
            "z.B. Zollpapiere, Zertifikate, Zeitnachweise"
        ),
    )
    prepaid_amount: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Bereits gezahlter Betrag (BT-113) — "
            "z.B. Abschlagszahlungen bei Schlussrechnungen"
        ),
    )

    @staticmethod
    def _line_net_amount(item: "LineItem") -> Decimal:
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


class ValidationError(BaseModel):
    code: str = Field(default="", description="Fehlercode")
    message: str = Field(..., description="Fehlermeldung")
    severity: str = Field(default="error", description="Schweregrad (error/warning)")
    location: str = Field(default="", description="XPath-Position im Dokument")


class ValidationResult(BaseModel):
    valid: bool = Field(..., description="Ist das Dokument gültig?")
    errors: list[ValidationError] = Field(default_factory=list, description="Fehler")
    warnings: list[ValidationError] = Field(default_factory=list, description="Warnungen")
    profile: str = Field(default="", description="Erkanntes Profil")
    raw_report: str = Field(default="", description="Vollständiger Prüfbericht (XML)")


class TaxBreakdown(BaseModel):
    tax_rate: Decimal
    tax_category: str
    taxable_amount: Decimal
    tax_amount: Decimal


class Totals(BaseModel):
    net_total: Decimal = Field(description="Summe der Nettopositionen (BT-106)")
    tax_basis_total: Decimal = Field(
        default=Decimal("0"),
        description="Steuerbemessungsgrundlage (BT-109) = BT-106 - Abschläge + Zuschläge",
    )
    tax_total: Decimal
    gross_total: Decimal
    prepaid_amount: Decimal = Field(default=Decimal("0"), description="Bereits gezahlt (BT-113)")
    due_payable: Decimal


class ParsedLineAllowanceCharge(BaseModel):
    charge: bool = Field(default=False, description="True=Zuschlag, False=Rabatt")
    amount: Decimal = Field(default=Decimal("0"), description="Betrag")
    reason: str = Field(default="", description="Grund")


class ParsedAllowanceCharge(BaseModel):
    charge: bool = Field(default=False, description="True=Zuschlag, False=Rabatt")
    amount: Decimal = Field(default=Decimal("0"), description="Betrag")
    reason: str = Field(default="", description="Grund")
    tax_rate: Decimal = Field(default=Decimal("0"), description="Steuersatz")
    tax_category: str = Field(default="S", description="Steuerkategorie")


class ParsedInvoice(BaseModel):
    invoice_id: str = Field(default="", description="Rechnungsnummer")
    type_code: str = Field(default="380", description="Rechnungsartcode (BT-3)")
    issue_date: str = Field(default="", description="Rechnungsdatum")
    seller: Party | None = Field(default=None, description="Verkäufer")
    buyer: Party | None = Field(default=None, description="Käufer")
    items: list[LineItem] = Field(default_factory=list, description="Positionen")
    allowances_charges: list[ParsedAllowanceCharge] = Field(
        default_factory=list, description="Zu-/Abschläge (BG-20/BG-21)"
    )
    totals: Totals | None = Field(default=None, description="Summen")
    tax_breakdown: list[TaxBreakdown] = Field(
        default_factory=list, description="Steueraufschlüsselung"
    )
    currency: str = Field(default="EUR", description="Währung")
    profile: str = Field(default="", description="Erkanntes Profil")
    delivery_party_name: str = Field(default="", description="Lieferort Name (BT-70)")
    delivery_street: str = Field(default="", description="Lieferort Straße (BT-75)")
    delivery_city: str = Field(default="", description="Lieferort Stadt (BT-77)")
    delivery_postal_code: str = Field(default="", description="Lieferort PLZ (BT-78)")
    delivery_country_code: str = Field(default="", description="Lieferort Land (BT-80)")
    delivery_date: str = Field(default="", description="Lieferdatum (BT-71)")
    service_period_start: str = Field(default="", description="Leistungszeitraum Beginn (BT-73)")
    service_period_end: str = Field(default="", description="Leistungszeitraum Ende (BT-74)")
    due_date: str = Field(default="", description="Fälligkeitsdatum (BT-9)")
    invoice_note: str = Field(default="", description="Freitext-Bemerkung (BT-22)")
    payment_terms: str = Field(default="", description="Zahlungsbedingungen (BT-20)")
    tax_exemption_reason: str = Field(
        default="", description="Befreiungsgrund (BT-120)"
    )
    tax_exemption_reason_code: str = Field(
        default="", description="Befreiungsgrund Code (BT-121)"
    )
    skonto_percent: str = Field(default="", description="Skonto-Prozentsatz")
    skonto_days: str = Field(default="", description="Skonto-Frist in Tagen")
    purchase_order_reference: str = Field(
        default="", description="Bestellnummer (BT-13)"
    )
    sales_order_reference: str = Field(
        default="", description="Auftragsbestätigung (BT-14)"
    )
    contract_reference: str = Field(
        default="", description="Vertragsnummer (BT-12)"
    )
    project_reference: str = Field(
        default="", description="Projektreferenz (BT-11)"
    )
    preceding_invoice_number: str = Field(
        default="", description="Vorherige Rechnungsnummer (BT-25)"
    )
    preceding_invoice_date: str = Field(
        default="", description="Datum der vorherigen Rechnung (BT-26)"
    )
    despatch_advice_reference: str = Field(
        default="", description="Lieferscheinnummer (BT-16)"
    )
    tender_or_lot_reference: str = Field(
        default="", description="Vergabe- / Losnummer (BT-17)"
    )
    invoiced_object_identifier: str = Field(
        default="", description="Kennung des Abrechnungsobjekts (BT-18)"
    )
    business_process_type: str = Field(
        default="", description="Geschäftsprozesstyp (BT-23)"
    )
    remittance_information: str = Field(
        default="", description="Verwendungszweck (BT-83)"
    )
    buyer_iban: str = Field(default="", description="IBAN des Käufers (BT-91)")
    mandate_reference_id: str = Field(
        default="", description="SEPA-Mandatsreferenz (BT-89)"
    )
    seller_tax_representative: "Party | None" = Field(
        default=None, description="Steuerlicher Vertreter des Verkäufers (BG-11)"
    )
    payee_name: str = Field(default="", description="Zahlungsempfänger Name (BT-59)")
    payee_id: str = Field(default="", description="Kennung des Zahlungsempfängers (BT-60)")
    payee_legal_registration_id: str = Field(
        default="", description="Handelsregisternummer des Zahlungsempfängers (BT-61)"
    )
    payment_card_pan: str = Field(
        default="", description="Zahlungskarten-PAN (BT-87)"
    )
    payment_card_holder: str = Field(
        default="", description="Name des Karteninhabers (BT-88)"
    )
    seller_iban: str = Field(default="", description="IBAN des Verkäufers (BT-84)")
    seller_bic: str = Field(default="", description="BIC des Verkäufers (BT-86)")
    seller_bank_name: str = Field(default="", description="Bankname des Verkäufers")
    receiving_advice_reference: str = Field(
        default="", description="Wareneingangsreferenz (BT-15)"
    )
    delivery_location_id: str = Field(
        default="", description="Kennung des Lieferorts (BT-71)"
    )
    payment_means_type_code: str = Field(
        default="", description="Zahlungsart-Code (BT-81, z.B. 58=SEPA)"
    )
    payment_means_text: str = Field(
        default="", description="Zahlungsart Freitext (BT-82)"
    )
    buyer_reference: str = Field(
        default="", description="Käufer-Referenz / Leitweg-ID (BT-10)"
    )
    supporting_documents: list["SupportingDocument"] = Field(
        default_factory=list,
        description="Zusätzliche Belegdokumente (BG-24)",
    )


class FieldCheck(BaseModel):
    field: str = Field(..., description="Feldbezeichnung (z.B. BT-10)")
    name: str = Field(..., description="Feldname")
    present: bool = Field(..., description="Ist das Feld vorhanden?")
    value: str = Field(default="", description="Aktueller Wert")
    required: bool = Field(default=True, description="Pflichtfeld?")


class ComplianceResult(BaseModel):
    valid: bool = Field(..., description="Gesamtergebnis: konform?")
    kosit_valid: bool | None = Field(default=None, description="KoSIT-Validierung bestanden?")
    field_checks: list[FieldCheck] = Field(
        default_factory=list, description="Einzelne Feldprüfungen"
    )
    missing_fields: list[str] = Field(default_factory=list, description="Fehlende Pflichtfelder")
    suggestions: list[str] = Field(
        default_factory=list, description="Verbesserungsvorschläge (auf Deutsch)"
    )
