from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from datetime import date as date_type

from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Document(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    title: str
    owner_user_id: Optional[str] = Field(default=None, index=True, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentType(SQLModel, table=True):
    """High-level classification for documents (e.g. Contract, NDA, Invoice)."""

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    key: str = Field(index=True)
    title: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentTypeAssignment(SQLModel, table=True):
    """Assign exactly one type to a document (enforced at application level)."""

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    document_id: str = Field(index=True, foreign_key="document.id")
    type_id: str = Field(index=True, foreign_key="documenttype.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentVersion(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    document_id: str = Field(index=True, foreign_key="document.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Where the original file/text is stored
    artifact_path: str
    content_type: str


class Task(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    kind: str = Field(index=True)
    status: TaskStatus = Field(default=TaskStatus.pending, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    document_id: Optional[str] = Field(default=None, index=True, foreign_key="document.id")
    version_id: Optional[str] = Field(default=None, index=True, foreign_key="documentversion.id")

    # Result artifact (optional)
    result_path: Optional[str] = None
    error: Optional[str] = None


class Organization(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(index=True)
    inn: Optional[str] = Field(default=None, index=True)
    ogrn: Optional[str] = None
    kpp: Optional[str] = None

    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TemplateFieldType(str, Enum):
    text = "text"
    number = "number"
    date = "date"
    boolean = "boolean"
    choice = "choice"
    organization_ref = "organization_ref"


class DocumentTemplate(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    title: str = Field(index=True)
    category: Optional[str] = Field(default=None, index=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentTemplateVersion(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    template_id: str = Field(index=True, foreign_key="documenttemplate.id")
    version: int = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Deterministic text template body (Jinja2)
    body: str


class DocumentTemplateField(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    template_version_id: str = Field(index=True, foreign_key="documenttemplateversion.id")

    key: str = Field(index=True)
    label: str
    field_type: TemplateFieldType = Field(index=True)
    required: bool = False
    order: int = 0

    # For choice fields
    options: Optional[list[str]] = Field(default=None, sa_column=Column(JSONB))
    default_value: Optional[str] = None


class GeneratedDocument(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    document_id: str = Field(index=True, foreign_key="document.id")
    template_version_id: str = Field(index=True, foreign_key="documenttemplateversion.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Persist the structured data used for rendering.
    data: dict[str, Any] = Field(sa_column=Column(JSONB))


class CalendarEventLink(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    version_id: str = Field(index=True, foreign_key="documentversion.id")
    google_calendar_id: str = Field(index=True)
    google_event_id: str = Field(index=True)
    start_date: date_type
    end_date: date_type
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GoogleOAuthConnection(SQLModel, table=True):
    """Stores a single connected Google account token set (MVP).

    NOTE: This is intentionally not a full user system yet.
    """

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    email: Optional[str] = Field(default=None, index=True)
    sub: Optional[str] = Field(default=None, index=True)

    access_token: str
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    scope: Optional[str] = None
    expires_at: Optional[datetime] = None


class GoogleDriveFileLink(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    version_id: str = Field(index=True, foreign_key="documentversion.id")
    drive_file_id: str = Field(index=True)
    web_view_link: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    email: str = Field(sa_column=Column(String, unique=True, index=True, nullable=False))

    password_hash: str

    # Seed phrase login (store lookup key + bcrypt hash)
    seed_key: str = Field(sa_column=Column(String, unique=True, index=True, nullable=False))
    seed_hash: str


class UserAIConfig(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    user_id: str = Field(index=True, foreign_key="user.id")

    provider: str = Field(default="openrouter", index=True)
    base_url: str = Field(default="https://openrouter.ai/api/v1")
    # Legacy single-key storage (kept for backward compatibility / simple MVP).
    api_key: str = Field(default="")
    # New multi-key storage: points at UserAPIKey when set.
    api_key_id: Optional[str] = Field(default=None, index=True, foreign_key="userapikey.id")
    model: str


class UserAPIKey(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    user_id: str = Field(index=True, foreign_key="user.id")
    provider: str = Field(default="openrouter", index=True)
    label: Optional[str] = None
    api_key: str


class LegalSubjectKind(str, Enum):
    person = "person"
    organization = "organization"
    government_body = "government_body"
    other = "other"


class LegalSubject(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    kind: LegalSubjectKind = Field(index=True)
    country_code: str = Field(default="RU", index=True)

    display_name: str = Field(index=True)

    # Optional link to requisites entity when the subject is an organization.
    organization_id: Optional[str] = Field(default=None, index=True, foreign_key="organization.id")

    # Person attributes (optional; used when kind=person)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    birth_date: Optional[date_type] = None

    # Contact/address
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RepresentationBasisKind(str, Enum):
    power_of_attorney = "power_of_attorney"
    charter = "charter"
    order = "order"
    other = "other"


class Representation(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    principal_subject_id: str = Field(index=True, foreign_key="legalsubject.id")
    agent_subject_id: str = Field(index=True, foreign_key="legalsubject.id")

    basis_kind: RepresentationBasisKind = Field(index=True)
    basis_number: Optional[str] = None
    basis_date: Optional[date_type] = None
    valid_from: Optional[date_type] = None
    valid_to: Optional[date_type] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ContractKind(str, Enum):
    services = "services"
    works = "works"
    supply = "supply"
    nda = "nda"
    lease = "lease"
    license = "license"
    mixed = "mixed"
    other = "other"


class Contract(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    title: str = Field(index=True)
    kind: ContractKind = Field(index=True)

    # RU-first. Future jurisdictions can be added by changing these fields.
    jurisdiction_country_code: str = Field(default="RU", index=True)
    governing_law_text: Optional[str] = None

    # Optional link to the document registry.
    document_id: Optional[str] = Field(default=None, index=True, foreign_key="document.id")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ContractParty(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    contract_id: str = Field(index=True, foreign_key="contract.id")
    subject_id: str = Field(index=True, foreign_key="legalsubject.id")

    role_key: str = Field(index=True)
    role_label: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContractObject(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    contract_id: str = Field(index=True, foreign_key="contract.id")

    kind: str = Field(index=True)
    title: str = Field(index=True)
    description: Optional[str] = None
    address: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContractEvent(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    contract_id: str = Field(index=True, foreign_key="contract.id")

    kind: str = Field(index=True)
    title: str

    start_date: Optional[date_type] = Field(default=None, index=True)
    end_date: Optional[date_type] = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContractCondition(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    contract_id: str = Field(index=True, foreign_key="contract.id")

    kind: str = Field(index=True)
    expression: str

    created_at: datetime = Field(default_factory=datetime.utcnow)


class NormativeStatementKind(str, Enum):
    obligation = "obligation"
    right = "right"
    prohibition = "prohibition"
    permission = "permission"


class NormativeStatement(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    contract_id: str = Field(index=True, foreign_key="contract.id")
    kind: NormativeStatementKind = Field(index=True)

    actor_party_id: str = Field(index=True, foreign_key="contractparty.id")
    counterparty_party_id: Optional[str] = Field(default=None, index=True, foreign_key="contractparty.id")

    object_id: Optional[str] = Field(default=None, index=True, foreign_key="contractobject.id")
    action_verb: Optional[str] = Field(default=None, index=True)
    description: str

    condition_id: Optional[str] = Field(default=None, index=True, foreign_key="contractcondition.id")
    due_event_id: Optional[str] = Field(default=None, index=True, foreign_key="contractevent.id")
    due_date: Optional[date_type] = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)


class PaymentTermKind(str, Enum):
    fixed_amount = "fixed_amount"
    percent_of_total = "percent_of_total"
    milestone = "milestone"
    other = "other"


class PaymentTerm(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    contract_id: str = Field(index=True, foreign_key="contract.id")

    payer_party_id: str = Field(index=True, foreign_key="contractparty.id")
    payee_party_id: str = Field(index=True, foreign_key="contractparty.id")

    kind: PaymentTermKind = Field(index=True)
    amount_minor: Optional[int] = None
    currency_code: str = Field(default="RUB", index=True)
    percent: Optional[float] = None

    due_event_id: Optional[str] = Field(default=None, index=True, foreign_key="contractevent.id")
    due_date: Optional[date_type] = Field(default=None, index=True)
    description: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContractClause(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    contract_id: str = Field(index=True, foreign_key="contract.id")

    kind: str = Field(index=True)
    title: Optional[str] = None
    body: Optional[str] = None
    data: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))

    created_at: datetime = Field(default_factory=datetime.utcnow)


class LegalNormReference(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    jurisdiction_country_code: str = Field(default="RU", index=True)
    citation: str = Field(index=True)
    url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClauseNormLink(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    clause_id: str = Field(index=True, foreign_key="contractclause.id")
    norm_id: str = Field(index=True, foreign_key="legalnormreference.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class StatementNormLink(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    statement_id: str = Field(index=True, foreign_key="normativestatement.id")
    norm_id: str = Field(index=True, foreign_key="legalnormreference.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
