"""Pydantic models for invoice data, validation results, and parsed output."""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


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
    allowances_charges: list["LineAllowanceCharge"] = Field(
        default_factory=list,
        max_length=50,
        description="Positions-Zu-/Abschläge (BG-27/BG-28)",
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
    despatch_advice_reference: str | None = Field(
        default=None,
        max_length=100,
        description="Lieferscheinnummer (BT-16)",
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

    def total_net(self) -> Decimal:
        """Sum of line item net amounts (BT-106)."""
        return sum(
            ((item.quantity * item.unit_price).quantize(Decimal("0.01")) for item in self.items),
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
            net = item.quantity * item.unit_price
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
    net_total: Decimal
    tax_total: Decimal
    gross_total: Decimal
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
    despatch_advice_reference: str = Field(
        default="", description="Lieferscheinnummer (BT-16)"
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
    seller_iban: str = Field(default="", description="IBAN des Verkäufers (BT-84)")
    seller_bic: str = Field(default="", description="BIC des Verkäufers (BT-86)")
    seller_bank_name: str = Field(default="", description="Bankname des Verkäufers")


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
