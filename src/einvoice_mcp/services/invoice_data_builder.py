"""Build InvoiceData from flat MCP tool parameters."""

import json

from pydantic import ValidationError as PydanticValidationError

from einvoice_mcp.models import InvoiceData, InvoiceProfile

# Valid profile values for user-facing error messages
_VALID_PROFILES = ", ".join(p.value for p in InvoiceProfile)

# Map Pydantic field paths to German BT descriptions for user-friendly errors
FIELD_TO_BT: dict[str, str] = {
    "invoice_id": "BT-1 (Rechnungsnummer)",
    "issue_date": "BT-2 (Rechnungsdatum)",
    "type_code": "BT-3 (Rechnungsart)",
    "currency": "BT-5 (Währung)",
    "seller": "BG-4 (Verkäufer)",
    "seller.name": "BT-27 (Verkäufername)",
    "seller.address": "BG-5 (Verkäuferadresse)",
    "seller.address.street": "BT-35 (Straße Verkäufer)",
    "seller.address.city": "BT-37 (Ort Verkäufer)",
    "seller.address.postal_code": "BT-38 (PLZ Verkäufer)",
    "seller.address.country_code": "BT-40 (Land Verkäufer)",
    "seller.tax_id": "BT-31 (USt-IdNr. Verkäufer)",
    "seller.electronic_address": "BT-34 (Elektr. Adresse Verkäufer)",
    "buyer": "BG-7 (Käufer)",
    "buyer.name": "BT-44 (Käufername)",
    "buyer.address": "BG-8 (Käuferadresse)",
    "buyer.address.street": "BT-50 (Straße Käufer)",
    "buyer.address.city": "BT-52 (Ort Käufer)",
    "buyer.address.postal_code": "BT-53 (PLZ Käufer)",
    "buyer.address.country_code": "BT-55 (Land Käufer)",
    "items": "BG-25 (Rechnungsposition)",
    "seller_iban": "BT-84 (IBAN)",
    "seller_bic": "BT-86 (BIC)",
    "leitweg_id": "BT-10 (Leitweg-ID)",
}


def format_pydantic_errors(exc: PydanticValidationError) -> str:
    """Format Pydantic validation errors with BT number references."""
    parts: list[str] = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(p) for p in err["loc"])
        bt_ref = FIELD_TO_BT.get(loc, loc)
        parts.append(f"{bt_ref}: {err['msg']}")
    return "Fehler: Ungültige Rechnungsdaten:\n" + "\n".join(f"  - {p}" for p in parts)


def build_invoice_data(
    *,
    invoice_id: str,
    issue_date: str,
    seller_name: str,
    seller_street: str,
    seller_city: str,
    seller_postal_code: str,
    seller_country_code: str,
    seller_tax_id: str,
    buyer_name: str,
    buyer_street: str,
    buyer_city: str,
    buyer_postal_code: str,
    buyer_country_code: str,
    items_json: str,
    seller_street_2: str = "",
    seller_street_3: str = "",
    seller_country_subdivision: str = "",
    buyer_street_2: str = "",
    buyer_street_3: str = "",
    buyer_country_subdivision: str = "",
    buyer_tax_id: str = "",
    currency: str = "EUR",
    payment_terms_days: int | None = None,
    leitweg_id: str = "",
    buyer_reference: str = "",
    profile: str = "XRECHNUNG",
    seller_electronic_address: str = "",
    seller_electronic_address_scheme: str = "EM",
    buyer_electronic_address: str = "",
    buyer_electronic_address_scheme: str = "EM",
    seller_contact_name: str = "",
    seller_contact_email: str = "",
    seller_contact_phone: str = "",
    buyer_contact_name: str = "",
    buyer_contact_email: str = "",
    buyer_contact_phone: str = "",
    seller_iban: str = "",
    seller_bic: str = "",
    seller_bank_name: str = "",
    type_code: str = "380",
    seller_tax_number: str = "",
    seller_registration_id: str = "",
    buyer_registration_id: str = "",
    delivery_party_name: str = "",
    delivery_street: str = "",
    delivery_city: str = "",
    delivery_postal_code: str = "",
    delivery_country_code: str = "",
    delivery_date: str = "",
    service_period_start: str = "",
    service_period_end: str = "",
    due_date: str = "",
    invoice_note: str = "",
    payment_terms_text: str = "",
    purchase_order_reference: str = "",
    sales_order_reference: str = "",
    contract_reference: str = "",
    project_reference: str = "",
    preceding_invoice_number: str = "",
    despatch_advice_reference: str = "",
    invoiced_object_identifier: str = "",
    business_process_type: str = "",
    buyer_iban: str = "",
    mandate_reference_id: str = "",
    skonto_percent: str = "",
    skonto_days: int | None = None,
    skonto_base_amount: str = "",
    payment_means_type_code: str = "58",
    remittance_information: str = "",
    allowances_charges_json: str = "",
    tax_exemption_reason: str = "",
    tax_exemption_reason_code: str = "",
    tender_or_lot_reference: str = "",
    seller_trading_name: str = "",
    buyer_trading_name: str = "",
    payee_name: str = "",
    payee_id: str = "",
    payee_legal_registration_id: str = "",
    payment_card_pan: str = "",
    payment_card_holder: str = "",
    seller_tax_rep_name: str = "",
    seller_tax_rep_street: str = "",
    seller_tax_rep_city: str = "",
    seller_tax_rep_postal_code: str = "",
    seller_tax_rep_country_code: str = "",
    seller_tax_rep_tax_id: str = "",
    receiving_advice_reference: str = "",
    delivery_location_id: str = "",
    payment_means_text: str = "",
    supporting_documents_json: str = "",
) -> InvoiceData | str:
    """Build InvoiceData from flat MCP tool parameters.

    Returns InvoiceData on success, or a German error string on failure.
    """
    try:
        items_list = json.loads(items_json)
    except json.JSONDecodeError:
        return "Fehler: 'items' muss ein gültiges JSON-Array sein."

    ac_list: list[dict[str, object]] = []
    if allowances_charges_json:
        try:
            ac_list = json.loads(allowances_charges_json)
        except json.JSONDecodeError:
            return "Fehler: 'allowances_charges' muss ein gültiges JSON-Array sein."

    sd_list: list[dict[str, object]] = []
    if supporting_documents_json:
        try:
            sd_list = json.loads(supporting_documents_json)
        except json.JSONDecodeError:
            return "Fehler: 'supporting_documents' muss ein gültiges JSON-Array sein."

    try:
        invoice_profile = InvoiceProfile(profile)
    except ValueError:
        return f"Fehler: Ungültiges Profil. Erlaubt: {_VALID_PROFILES}."

    try:
        return InvoiceData.model_validate(
            {
                "invoice_id": invoice_id,
                "issue_date": issue_date,
                "type_code": type_code,
                "seller": {
                    "name": seller_name,
                    "address": {
                        "street": seller_street,
                        "street_2": seller_street_2 or None,
                        "street_3": seller_street_3 or None,
                        "city": seller_city,
                        "postal_code": seller_postal_code,
                        "country_code": seller_country_code,
                        "country_subdivision": seller_country_subdivision or None,
                    },
                    "tax_id": seller_tax_id or None,
                    "tax_number": seller_tax_number or None,
                    "registration_id": seller_registration_id or None,
                    "electronic_address": seller_electronic_address or None,
                    "electronic_address_scheme": seller_electronic_address_scheme,
                    "trading_name": seller_trading_name or None,
                },
                "buyer": {
                    "name": buyer_name,
                    "address": {
                        "street": buyer_street,
                        "street_2": buyer_street_2 or None,
                        "street_3": buyer_street_3 or None,
                        "city": buyer_city,
                        "postal_code": buyer_postal_code,
                        "country_code": buyer_country_code,
                        "country_subdivision": buyer_country_subdivision or None,
                    },
                    "tax_id": buyer_tax_id or None,
                    "registration_id": buyer_registration_id or None,
                    "electronic_address": buyer_electronic_address or None,
                    "electronic_address_scheme": buyer_electronic_address_scheme,
                    "trading_name": buyer_trading_name or None,
                },
                "items": items_list,
                "allowances_charges": ac_list,
                "currency": currency,
                "payment_terms_days": payment_terms_days,
                "leitweg_id": leitweg_id or None,
                "buyer_reference": buyer_reference or None,
                "profile": invoice_profile,
                "seller_contact_name": seller_contact_name or None,
                "seller_contact_email": seller_contact_email or None,
                "seller_contact_phone": seller_contact_phone or None,
                "buyer_contact_name": buyer_contact_name or None,
                "buyer_contact_email": buyer_contact_email or None,
                "buyer_contact_phone": buyer_contact_phone or None,
                "seller_iban": seller_iban or None,
                "seller_bic": seller_bic or None,
                "seller_bank_name": seller_bank_name or None,
                "delivery_party_name": delivery_party_name or None,
                "delivery_street": delivery_street or None,
                "delivery_city": delivery_city or None,
                "delivery_postal_code": delivery_postal_code or None,
                "delivery_country_code": delivery_country_code or None,
                "delivery_date": delivery_date or None,
                "service_period_start": service_period_start or None,
                "service_period_end": service_period_end or None,
                "due_date": due_date or None,
                "invoice_note": invoice_note or None,
                "payment_terms_text": payment_terms_text or None,
                "purchase_order_reference": purchase_order_reference or None,
                "sales_order_reference": sales_order_reference or None,
                "contract_reference": contract_reference or None,
                "project_reference": project_reference or None,
                "preceding_invoice_number": preceding_invoice_number or None,
                "despatch_advice_reference": despatch_advice_reference or None,
                "invoiced_object_identifier": invoiced_object_identifier or None,
                "business_process_type": business_process_type or None,
                "buyer_iban": buyer_iban or None,
                "mandate_reference_id": mandate_reference_id or None,
                "skonto_percent": skonto_percent or None,
                "skonto_days": skonto_days,
                "skonto_base_amount": skonto_base_amount or None,
                "payment_means_type_code": payment_means_type_code,
                "remittance_information": remittance_information or None,
                "tax_exemption_reason": tax_exemption_reason or None,
                "tax_exemption_reason_code": tax_exemption_reason_code or None,
                "tender_or_lot_reference": tender_or_lot_reference or None,
                "payee_name": payee_name or None,
                "payee_id": payee_id or None,
                "payee_legal_registration_id": payee_legal_registration_id or None,
                "payment_card_pan": payment_card_pan or None,
                "payment_card_holder": payment_card_holder or None,
                "receiving_advice_reference": receiving_advice_reference or None,
                "delivery_location_id": delivery_location_id or None,
                "payment_means_text": payment_means_text or None,
                "supporting_documents": sd_list,
                **(
                    {
                        "seller_tax_representative": {
                            "name": seller_tax_rep_name,
                            "address": {
                                "street": seller_tax_rep_street,
                                "city": seller_tax_rep_city,
                                "postal_code": seller_tax_rep_postal_code,
                                "country_code": seller_tax_rep_country_code or "DE",
                            },
                            "tax_id": seller_tax_rep_tax_id or None,
                        }
                    }
                    if seller_tax_rep_name
                    else {}
                ),
            }
        )
    except PydanticValidationError as exc:
        return format_pydantic_errors(exc)
