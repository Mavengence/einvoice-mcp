"""Validation result, parsed invoice, and compliance result models."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from einvoice_mcp.models.line_items import LineItem, SupportingDocument
from einvoice_mcp.models.party import Party


class ValidationError(BaseModel):
    code: str = Field(default="", description="Fehlercode")
    message: str = Field(..., description="Fehlermeldung")
    severity: str = Field(default="error", description="Schweregrad (error/warning)")
    location: str = Field(default="", description="XPath-Position im Dokument")


class ValidationResult(BaseModel):
    valid: bool = Field(..., description="Ist das Dokument gueltig?")
    errors: list[ValidationError] = Field(default_factory=list, description="Fehler")
    warnings: list[ValidationError] = Field(default_factory=list, description="Warnungen")
    profile: str = Field(default="", description="Erkanntes Profil")
    raw_report: str = Field(default="", description="Vollstaendiger Pruefbericht (XML)")


class TaxBreakdown(BaseModel):
    tax_rate: Decimal
    tax_category: str
    taxable_amount: Decimal
    tax_amount: Decimal


class Totals(BaseModel):
    net_total: Decimal = Field(description="Summe der Nettopositionen (BT-106)")
    tax_basis_total: Decimal = Field(
        default=Decimal("0"),
        description="Steuerbemessungsgrundlage (BT-109) = BT-106 - Abschlaege + Zuschlaege",
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
    seller: Party | None = Field(default=None, description="Verkaeufer")
    buyer: Party | None = Field(default=None, description="Kaeufer")
    items: list[LineItem] = Field(default_factory=list, description="Positionen")
    allowances_charges: list[ParsedAllowanceCharge] = Field(
        default_factory=list, description="Zu-/Abschlaege (BG-20/BG-21)"
    )
    totals: Totals | None = Field(default=None, description="Summen")
    tax_breakdown: list[TaxBreakdown] = Field(
        default_factory=list, description="Steueraufschluesselung"
    )
    currency: str = Field(default="EUR", description="Waehrung")
    profile: str = Field(default="", description="Erkanntes Profil")
    delivery_party_name: str = Field(default="", description="Lieferort Name (BT-70)")
    delivery_street: str = Field(default="", description="Lieferort Strasse (BT-75)")
    delivery_city: str = Field(default="", description="Lieferort Stadt (BT-77)")
    delivery_postal_code: str = Field(default="", description="Lieferort PLZ (BT-78)")
    delivery_country_code: str = Field(default="", description="Lieferort Land (BT-80)")
    delivery_date: str = Field(default="", description="Lieferdatum (BT-72)")
    service_period_start: str = Field(default="", description="Leistungszeitraum Beginn (BT-73)")
    service_period_end: str = Field(default="", description="Leistungszeitraum Ende (BT-74)")
    due_date: str = Field(default="", description="Faelligkeitsdatum (BT-9)")
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
        default="", description="Auftragsbestaetigung (BT-14)"
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
        default="", description="Geschaeftsprozesstyp (BT-23)"
    )
    remittance_information: str = Field(
        default="", description="Verwendungszweck (BT-83)"
    )
    buyer_iban: str = Field(default="", description="IBAN des Kaeufers (BT-91)")
    mandate_reference_id: str = Field(
        default="", description="SEPA-Mandatsreferenz (BT-89)"
    )
    seller_tax_representative: Party | None = Field(
        default=None, description="Steuerlicher Vertreter des Verkaeufers (BG-11)"
    )
    payee_name: str = Field(default="", description="Zahlungsempfaenger Name (BT-59)")
    payee_id: str = Field(default="", description="Kennung des Zahlungsempfaengers (BT-60)")
    payee_legal_registration_id: str = Field(
        default="", description="Handelsregisternummer des Zahlungsempfaengers (BT-61)"
    )
    payment_card_pan: str = Field(
        default="", description="Zahlungskarten-PAN (BT-87)"
    )
    payment_card_holder: str = Field(
        default="", description="Name des Karteninhabers (BT-88)"
    )
    seller_iban: str = Field(default="", description="IBAN des Verkaeufers (BT-84)")
    seller_bic: str = Field(default="", description="BIC des Verkaeufers (BT-86)")
    seller_bank_name: str = Field(default="", description="Bankname des Verkaeufers")
    receiving_advice_reference: str = Field(
        default="", description="Wareneingangsreferenz (BT-15)"
    )
    delivery_location_id: str = Field(
        default="", description="Kennung des Lieferorts"
    )
    payment_means_type_code: str = Field(
        default="", description="Zahlungsart-Code (BT-81, z.B. 58=SEPA)"
    )
    payment_means_text: str = Field(
        default="", description="Zahlungsart Freitext (BT-82)"
    )
    buyer_reference: str = Field(
        default="", description="Kaeufer-Referenz / Leitweg-ID (BT-10)"
    )
    supporting_documents: list[SupportingDocument] = Field(
        default_factory=list,
        description="Zusaetzliche Belegdokumente (BG-24)",
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
        default_factory=list, description="Einzelne Feldpruefungen"
    )
    missing_fields: list[str] = Field(default_factory=list, description="Fehlende Pflichtfelder")
    suggestions: list[str] = Field(
        default_factory=list, description="Verbesserungsvorschlaege (auf Deutsch)"
    )
