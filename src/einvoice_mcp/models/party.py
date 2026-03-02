"""Party and address models."""

from pydantic import BaseModel, Field, field_validator


class Address(BaseModel):
    street: str = Field(..., min_length=1, max_length=200, description="Strasse und Hausnummer")
    street_2: str | None = Field(
        default=None, max_length=200, description="Adresszeile 2 (BT-36/BT-51)"
    )
    street_3: str | None = Field(
        default=None, max_length=200, description="Adresszeile 3 (BT-37/BT-52)"
    )
    city: str = Field(..., min_length=1, max_length=100, description="Stadt")
    postal_code: str = Field(..., min_length=1, max_length=20, description="Postleitzahl")
    country_code: str = Field(
        default="DE", min_length=2, max_length=2, description="ISO 3166-1 alpha-2 Laendercode"
    )
    country_subdivision: str | None = Field(
        default=None,
        max_length=100,
        description="Bundesland / Region (BT-39/BT-54, z.B. 'BY' fuer Bayern)",
    )

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        if not v.isalpha() or not v.isupper():
            raise ValueError(
                f"Ungültiger Ländercode '{v}'. ISO 3166-1 alpha-2 erwartet (z.B. DE, AT, CH)."
            )
        return v


class Party(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Vollstaendiger Name")
    trading_name: str | None = Field(
        default=None,
        max_length=200,
        description="Handelsname (BT-28/BT-45) -- falls abweichend vom rechtlichen Namen",
    )
    address: Address
    tax_id: str | None = Field(
        default=None, max_length=30, description="USt-IdNr. (BT-31, z.B. DE123456789)"
    )
    tax_number: str | None = Field(
        default=None,
        max_length=30,
        description="Steuernummer (BT-32, z.B. 123/456/78901) -- alternativ zu USt-IdNr.",
    )
    registration_id: str | None = Field(
        default=None, max_length=50, description="Handelsregisternummer oder GLN"
    )
    registration_id_scheme: str = Field(
        default="0088",
        max_length=10,
        description="Schema der Kennung (0088=GLN, 0060=DUNS, 0204=Leitweg-ID)",
    )
    electronic_address: str | None = Field(
        default=None,
        max_length=200,
        description="Elektronische Adresse (BT-34/BT-49), z.B. E-Mail oder Peppol-ID",
    )
    electronic_address_scheme: str = Field(
        default="EM",
        max_length=10,
        description="EAS-Code fuer elektronische Adresse (EM=E-Mail, 9930=USt-IdNr.)",
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
