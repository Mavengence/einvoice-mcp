"""MCP resource definitions for the einvoice-mcp server."""

from einvoice_mcp.resources.compliance_data import (
    br_de_rules,
    credit_note_reasons,
    e_rechnung_pflichten,
    skr03_mapping,
    skr04_mapping,
)
from einvoice_mcp.resources.reference_data import (
    example_line_items,
    reference_currency_codes,
    reference_eas_codes,
    reference_payment_means_codes,
    reference_tax_categories,
    reference_type_codes,
    reference_unit_codes,
    reference_vatex_codes,
)
from einvoice_mcp.resources.reference_data_advanced import (
    business_process_identifiers,
    cpv_classification_codes,
    leitweg_id_format,
    sepa_mandate_type_codes,
    tax_category_decision_tree,
    uncl_5189_allowance_reason_codes,
    vat_exemption_reason_texts,
)
from einvoice_mcp.resources.schemas import (
    schema_allowance_charge,
    schema_invoice_data,
    schema_item_attribute,
    schema_line_item,
    schema_supporting_document,
)

__all__ = [
    "br_de_rules",
    "business_process_identifiers",
    "cpv_classification_codes",
    "credit_note_reasons",
    "e_rechnung_pflichten",
    "example_line_items",
    "leitweg_id_format",
    "reference_currency_codes",
    "reference_eas_codes",
    "reference_payment_means_codes",
    "reference_tax_categories",
    "reference_type_codes",
    "reference_unit_codes",
    "reference_vatex_codes",
    "schema_allowance_charge",
    "schema_invoice_data",
    "schema_item_attribute",
    "schema_line_item",
    "schema_supporting_document",
    "sepa_mandate_type_codes",
    "skr03_mapping",
    "skr04_mapping",
    "tax_category_decision_tree",
    "uncl_5189_allowance_reason_codes",
    "vat_exemption_reason_texts",
]
