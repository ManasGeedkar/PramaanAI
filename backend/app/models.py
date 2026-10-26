from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    application_no: str = Field(index=True)
    institution_id: str = Field(index=True)
    institution_name: str
    aicte_id: str = Field(index=True)
    category: str = Field(default="EoA")
    academic_year: str = Field(default="2027-28")
    submitted_on: str
    status: str = Field(default="processing", index=True)  # processing | validated | under_review | evidence_requested | escalated | closed
    risk_score: float = Field(default=0.0)
    risk_band: Optional[str] = Field(default=None, index=True)  # Low | Medium | High
    risk_breakdown_json: Optional[str] = None
    folder: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    documents: List["Document"] = Relationship(back_populates="application")
    findings: List["Finding"] = Relationship(back_populates="application")


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="application.id", index=True)
    doc_type: str = Field(index=True)
    file_path: str
    sha256: str = Field(index=True)
    scanned: bool = Field(default=False)
    page_count: int = Field(default=1)
    producer: Optional[str] = None
    creation_date: Optional[str] = None
    mod_date: Optional[str] = None
    ocr_confidence: Optional[float] = None
    quality_json: Optional[str] = None  # JSON: {blur_variance, effective_dpi, mean_brightness, contrast, ela_assessable}
    ela_status: Optional[str] = None  # "not assessable" or None


    application: Optional[Application] = Relationship(back_populates="documents")
    fields: List["ExtractedField"] = Relationship(back_populates="document")
    findings: List["Finding"] = Relationship(back_populates="document")
    verifications: List["Verification"] = Relationship(back_populates="document")


class ExtractedField(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    name: str = Field(index=True)
    value: Optional[str] = None
    page: int = Field(default=1)
    bbox_json: Optional[str] = None  # JSON: [x0, y0, x1, y1]
    confidence: Optional[float] = None

    document: Optional[Document] = Relationship(back_populates="fields")


class Finding(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="application.id", index=True)
    document_id: Optional[int] = Field(default=None, foreign_key="document.id", index=True)
    code: str = Field(index=True)  # Section 4.2 Finding codes
    severity: str = Field(index=True)  # critical | warning | info
    title: str
    message: str
    rule_id: Optional[str] = None
    evidence_json: Optional[str] = None  # Section 4.3 evidence_json shape
    confidence: Optional[float] = None
    status: str = Field(default="open", index=True)  # open | accepted | dismissed | evidence_requested | escalated
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    application: Optional[Application] = Relationship(back_populates="findings")
    document: Optional[Document] = Relationship(back_populates="findings")
    reviews: List["Review"] = Relationship(
        back_populates="finding",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class Verification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    source: str  # fire_noc | land_registry | university | accreditation | aicte
    reference: str
    status: str = Field(index=True)  # verified | mismatch | expired | pending | source_unavailable | manual_review
    details_json: Optional[str] = None
    checked_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    document: Optional[Document] = Relationship(back_populates="verifications")


class Entity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_type: str = Field(index=True)  # faculty | fire_noc_no | deed_no | survey_no | photo
    key: str = Field(index=True)
    display: str

    occurrences: List["EntityOccurrence"] = Relationship(back_populates="entity")


class EntityOccurrence(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_id: int = Field(foreign_key="entity.id", index=True)
    application_id: int = Field(foreign_key="application.id", index=True)
    document_id: int = Field(foreign_key="document.id", index=True)
    academic_year: str = Field(index=True)
    bbox_json: Optional[str] = None

    entity: Optional[Entity] = Relationship(back_populates="occurrences")


class Review(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    finding_id: int = Field(foreign_key="finding.id", index=True)
    reviewer: str
    decision: str  # accept | dismiss | request_evidence | escalate
    comment: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    finding: Optional[Finding] = Relationship(back_populates="reviews")


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    actor: str
    action: str
    entity_type: str
    entity_id: str
    payload_json: Optional[str] = None
    prev_hash: str
    hash: str


class RuleSet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    version: str
    yaml_text: str
    active: bool = Field(default=True)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
