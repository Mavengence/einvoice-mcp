"""Line item, allowance/charge, and supporting document models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from einvoice_mcp.models.enums import TaxCategory


class ItemAttribute(BaseModel):
    """Item attribute name/value pair (BG-30, BT-160/BT-161).

    Used for product characteristics like color, size, batch codes.
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Attributname (BT-160, z.B. 'Farbe', 'Groesse')",
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Attributwert (BT-161, z.B. 'Rot', 'XL')",
    )


class LineAllowanceCharge(BaseModel):
    """Line-level allowance or charge (BG-27/BG-28).

    charge=False -> line allowance/discount (BT-136..BT-139)
    charge=True  -> line charge/surcharge (BT-141..BT-144)
    """

    charge: bool = Field(
        default=False,
        description="True=Zuschlag, False=Abzug/Rabatt",
    )
    amount: Decimal = Field(..., ge=0, description="Betrag (BT-136/BT-141)")
    reason: str = Field(default="", max_length=500, description="Grund (BT-139/BT-144)")


class LineItem(BaseModel):
    line_id: str | None = Field(
        default=None,
        max_length=50,
        description="Positionsnummer (BT-126) -- Standard: automatisch 1,2,3...",
    )
    description: str = Field(..., min_length=1, max_length=500, description="Positionsbeschreibung")
    quantity: Decimal = Field(..., gt=0, description="Menge")
    unit_code: str = Field(
        default="H87", max_length=10, description="UN/ECE Einheitencode (H87=Stueck, HUR=Stunde)"
    )
    unit_price: Decimal = Field(..., ge=0, description="Netto-Einzelpreis in EUR")
    tax_rate: Decimal = Field(default=Decimal("19.00"), ge=0, le=100, description="Steuersatz in %")
    tax_category: TaxCategory = Field(default=TaxCategory.S, description="Steuerkategorie")
    seller_item_id: str | None = Field(
        default=None, max_length=100, description="Artikelnummer des Verkaeufers (BT-155)"
    )
    buyer_item_id: str | None = Field(
        default=None, max_length=100, description="Artikelnummer des Kaeufers (BT-156)"
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
        description="Brutto-Einzelpreis (BT-148) -- vor Abzug von Rabatten",
    )
    item_price_discount: Decimal | None = Field(
        default=None,
        ge=0,
        description="Preisabschlag pro Einheit (BT-147) -- Brutto-/Netto-Differenz",
    )
    item_classification_id: str | None = Field(
        default=None,
        max_length=100,
        description=("Klassifizierungscode (BT-158) -- z.B. CPV-Code fuer oeffentliche Vergabe"),
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
    allowances_charges: list[LineAllowanceCharge] = Field(
        default_factory=list,
        max_length=50,
        description="Positions-Zu-/Abschlaege (BG-27/BG-28)",
    )
    buyer_accounting_reference: str | None = Field(
        default=None,
        max_length=200,
        description="Kontierungsreferenz des Kaeufers (BT-133)",
    )
    line_period_start: date | None = Field(
        default=None,
        description="Abrechnungszeitraum Beginn (BT-134) -- fuer wiederkehrende Leistungen",
    )
    line_period_end: date | None = Field(
        default=None,
        description="Abrechnungszeitraum Ende (BT-135) -- fuer wiederkehrende Leistungen",
    )
    item_country_of_origin: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Ursprungsland des Artikels (BT-159, ISO 3166-1 alpha-2)",
    )
    attributes: list[ItemAttribute] = Field(
        default_factory=list,
        max_length=50,
        description="Artikelmerkmale (BG-30, BT-160/BT-161) -- Name/Wert-Paare",
    )
    line_object_identifier: str | None = Field(
        default=None,
        max_length=200,
        description="Kennung des Abrechnungsobjekts (BT-128) -- z.B. Vertragsnr.",
    )
    line_object_identifier_scheme: str = Field(
        default="AWV",
        max_length=20,
        description="Schema der Abrechnungsobjekt-Kennung (BT-128-1)",
    )
    line_purchase_order_reference: str | None = Field(
        default=None,
        max_length=100,
        description="Bestellpositionsnummer (BT-132) -- Referenz zur Bestellposition",
    )


class AllowanceCharge(BaseModel):
    """Document-level allowance or charge (BG-20/BG-21).

    charge=False -> allowance/discount (BT-92..BT-99)
    charge=True  -> surcharge/charge (BT-99..BT-105)
    """

    charge: bool = Field(
        default=False,
        description="True=Zuschlag, False=Abzug/Rabatt",
    )
    amount: Decimal = Field(..., ge=0, description="Betrag (BT-92/BT-99)")
    reason: str = Field(default="", max_length=500, description="Grund (BT-97/BT-104)")
    reason_code: str = Field(default="", max_length=10, description="Grundcode (BT-98/BT-105)")
    tax_rate: Decimal = Field(default=Decimal("19.00"), ge=0, le=100, description="Steuersatz in %")
    tax_category: TaxCategory = Field(default=TaxCategory.S, description="Steuerkategorie")
    base_amount: Decimal | None = Field(
        default=None, ge=0, description="Basisbetrag fuer Prozentberechnung (BT-93/BT-100)"
    )
    percentage: Decimal | None = Field(
        default=None, ge=0, le=100, description="Prozentsatz (BT-94/BT-101)"
    )


class SupportingDocument(BaseModel):
    """Additional supporting document (BG-24, BT-122..BT-125).

    Attach invoices, customs documents, certificates, or other files.
    """

    id: str = Field(
        ...,
        min_length=1,
        max_length=200,
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
