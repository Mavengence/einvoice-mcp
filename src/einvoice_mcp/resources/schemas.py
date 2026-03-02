"""JSON schema resources for InvoiceData models."""

import json

from einvoice_mcp.models import (
    AllowanceCharge,
    InvoiceData,
    ItemAttribute,
    LineItem,
    SupportingDocument,
)


def schema_line_item() -> str:
    """JSON-Schema für eine Rechnungsposition (items-Array-Element).

    Verwenden Sie dieses Schema um korrekte JSON-Objekte für den
    'items' Parameter der generate-Tools zu erstellen.
    """
    return json.dumps(LineItem.model_json_schema(), ensure_ascii=False, indent=2)


def schema_allowance_charge() -> str:
    """JSON-Schema für Zu-/Abschläge (allowances_charges-Array-Element).

    Verwenden Sie dieses Schema um korrekte JSON-Objekte für den
    'allowances_charges' Parameter der generate-Tools zu erstellen.
    """
    return json.dumps(AllowanceCharge.model_json_schema(), ensure_ascii=False, indent=2)


def schema_item_attribute() -> str:
    """JSON-Schema für Artikelmerkmale (BG-30, BT-160/BT-161).

    Name/Wert-Paare für Produkteigenschaften wie Farbe, Größe, Material.
    """
    return json.dumps(ItemAttribute.model_json_schema(), ensure_ascii=False, indent=2)


def schema_supporting_document() -> str:
    """JSON-Schema für zusätzliche Belegdokumente (BG-24, BT-122..BT-125).

    Anhänge wie Zollpapiere, Zertifikate, Zeitnachweise.
    """
    return json.dumps(SupportingDocument.model_json_schema(), ensure_ascii=False, indent=2)


def schema_invoice_data() -> str:
    """Vollständiges JSON-Schema für InvoiceData.

    Zeigt alle verfügbaren Felder mit Typen, Beschreibungen und
    Validierungsregeln für die Rechnungserstellung.
    """
    return json.dumps(InvoiceData.model_json_schema(), ensure_ascii=False, indent=2)
