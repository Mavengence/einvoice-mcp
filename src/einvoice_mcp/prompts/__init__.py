"""MCP prompt definitions for the einvoice-mcp server."""

from einvoice_mcp.prompts.guides import (
    abschlagsrechnung_guide,
    b2b_pflicht_2027,
    bauleistungen_13b_guide,
    differenzbesteuerung_25a_guide,
    gutschrift_erstellen,
    handwerkerrechnung_35a,
    kleinunternehmer_guide,
    korrekturrechnung_erstellen,
    ratenzahlung_rechnung,
    reverse_charge_checkliste,
    steuerprüfung_checkliste,
    stornobuchung_workflow,
    typecode_entscheidungshilfe,
    xrechnung_schnellstart,
)
from einvoice_mcp.prompts.guides_advanced import (
    dauerrechnung_guide,
    innergemeinschaftliche_lieferung_guide,
    reiseleistungen_25_guide,
    steuernummer_vs_ustidnr_guide,
)

__all__ = [
    "abschlagsrechnung_guide",
    "b2b_pflicht_2027",
    "bauleistungen_13b_guide",
    "dauerrechnung_guide",
    "differenzbesteuerung_25a_guide",
    "gutschrift_erstellen",
    "handwerkerrechnung_35a",
    "innergemeinschaftliche_lieferung_guide",
    "kleinunternehmer_guide",
    "korrekturrechnung_erstellen",
    "ratenzahlung_rechnung",
    "reiseleistungen_25_guide",
    "reverse_charge_checkliste",
    "steuernummer_vs_ustidnr_guide",
    "steuerprüfung_checkliste",
    "stornobuchung_workflow",
    "typecode_entscheidungshilfe",
    "xrechnung_schnellstart",
]
