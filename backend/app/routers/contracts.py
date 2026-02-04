from __future__ import annotations

from datetime import date as date_type
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from ..db import get_session
from ..models import (
    ClauseNormLink,
    Contract,
    ContractClause,
    ContractCondition,
    ContractEvent,
    ContractObject,
    ContractParty,
    ContractKind,
    LegalNormReference,
    LegalSubject,
    LegalSubjectKind,
    NormativeStatement,
    NormativeStatementKind,
    PaymentTerm,
    PaymentTermKind,
    Representation,
    RepresentationBasisKind,
    StatementNormLink,
)

router = APIRouter(tags=["legal"], prefix="")


def _trim(s: str | None) -> str | None:
    if s is None:
        return None
    t = s.strip()
    return t or None


class LegalSubjectCreateRequest(BaseModel):
    kind: LegalSubjectKind
    country_code: str | None = "RU"
    display_name: str

    organization_id: str | None = None

    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    birth_date: date_type | None = None

    address: str | None = None
    phone: str | None = None
    email: str | None = None


class LegalSubjectUpdateRequest(BaseModel):
    kind: LegalSubjectKind | None = None
    country_code: str | None = None
    display_name: str | None = None

    organization_id: str | None = None

    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    birth_date: date_type | None = None

    address: str | None = None
    phone: str | None = None
    email: str | None = None


@router.get("/legal-subjects")
def list_legal_subjects() -> list[LegalSubject]:
    with get_session() as session:
        return list(
            session.exec(select(LegalSubject).order_by(LegalSubject.display_name.asc())).all()
        )


@router.post("/legal-subjects")
def create_legal_subject(req: LegalSubjectCreateRequest) -> LegalSubject:
    display_name = (req.display_name or "").strip()
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name is required")

    subject = LegalSubject(
        kind=req.kind,
        country_code=(req.country_code or "RU").strip() or "RU",
        display_name=display_name,
        organization_id=_trim(req.organization_id),
        first_name=_trim(req.first_name),
        last_name=_trim(req.last_name),
        middle_name=_trim(req.middle_name),
        birth_date=req.birth_date,
        address=_trim(req.address),
        phone=_trim(req.phone),
        email=_trim(req.email),
    )

    with get_session() as session:
        session.add(subject)
        session.commit()
        session.refresh(subject)
        return subject


@router.get("/legal-subjects/{subject_id}")
def get_legal_subject(subject_id: str) -> LegalSubject:
    with get_session() as session:
        subject = session.get(LegalSubject, subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Legal subject not found")
        return subject


@router.patch("/legal-subjects/{subject_id}")
def update_legal_subject(subject_id: str, req: LegalSubjectUpdateRequest) -> LegalSubject:
    with get_session() as session:
        subject = session.get(LegalSubject, subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Legal subject not found")

        changed = False
        if req.kind is not None:
            subject.kind = req.kind
            changed = True
        if req.country_code is not None:
            subject.country_code = (req.country_code or "").strip() or "RU"
            changed = True
        if req.display_name is not None:
            dn = (req.display_name or "").strip()
            if not dn:
                raise HTTPException(status_code=400, detail="display_name cannot be empty")
            subject.display_name = dn
            changed = True

        if req.organization_id is not None:
            subject.organization_id = _trim(req.organization_id)
            changed = True

        if req.first_name is not None:
            subject.first_name = _trim(req.first_name)
            changed = True
        if req.last_name is not None:
            subject.last_name = _trim(req.last_name)
            changed = True
        if req.middle_name is not None:
            subject.middle_name = _trim(req.middle_name)
            changed = True
        if req.birth_date is not None:
            subject.birth_date = req.birth_date
            changed = True

        if req.address is not None:
            subject.address = _trim(req.address)
            changed = True
        if req.phone is not None:
            subject.phone = _trim(req.phone)
            changed = True
        if req.email is not None:
            subject.email = _trim(req.email)
            changed = True

        if changed:
            subject.updated_at = datetime.utcnow()
            session.add(subject)
            session.commit()
            session.refresh(subject)

        return subject


class RepresentationCreateRequest(BaseModel):
    principal_subject_id: str
    agent_subject_id: str
    basis_kind: RepresentationBasisKind
    basis_number: str | None = None
    basis_date: date_type | None = None
    valid_from: date_type | None = None
    valid_to: date_type | None = None


@router.get("/representations")
def list_representations() -> list[Representation]:
    with get_session() as session:
        return list(session.exec(select(Representation).order_by(Representation.created_at.desc())).all())


@router.post("/representations")
def create_representation(req: RepresentationCreateRequest) -> Representation:
    rep = Representation(
        principal_subject_id=req.principal_subject_id,
        agent_subject_id=req.agent_subject_id,
        basis_kind=req.basis_kind,
        basis_number=_trim(req.basis_number),
        basis_date=req.basis_date,
        valid_from=req.valid_from,
        valid_to=req.valid_to,
    )

    with get_session() as session:
        if not session.get(LegalSubject, req.principal_subject_id):
            raise HTTPException(status_code=404, detail="principal_subject_id not found")
        if not session.get(LegalSubject, req.agent_subject_id):
            raise HTTPException(status_code=404, detail="agent_subject_id not found")

        session.add(rep)
        session.commit()
        session.refresh(rep)
        return rep


class ContractCreateRequest(BaseModel):
    title: str
    kind: ContractKind
    jurisdiction_country_code: str | None = "RU"
    governing_law_text: str | None = None
    document_id: str | None = None


class ContractUpdateRequest(BaseModel):
    title: str | None = None
    kind: ContractKind | None = None
    jurisdiction_country_code: str | None = None
    governing_law_text: str | None = None
    document_id: str | None = None


@router.get("/contracts")
def list_contracts() -> list[Contract]:
    with get_session() as session:
        return list(session.exec(select(Contract).order_by(Contract.created_at.desc())).all())


@router.post("/contracts")
def create_contract(req: ContractCreateRequest) -> Contract:
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    contract = Contract(
        title=title,
        kind=req.kind,
        jurisdiction_country_code=(req.jurisdiction_country_code or "RU").strip() or "RU",
        governing_law_text=_trim(req.governing_law_text),
        document_id=_trim(req.document_id),
    )

    with get_session() as session:
        session.add(contract)
        session.commit()
        session.refresh(contract)
        return contract


@router.get("/contracts/{contract_id}")
def get_contract(contract_id: str) -> Contract:
    with get_session() as session:
        contract = session.get(Contract, contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        return contract


@router.patch("/contracts/{contract_id}")
def update_contract(contract_id: str, req: ContractUpdateRequest) -> Contract:
    with get_session() as session:
        contract = session.get(Contract, contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        changed = False
        if req.title is not None:
            title = (req.title or "").strip()
            if not title:
                raise HTTPException(status_code=400, detail="title cannot be empty")
            contract.title = title
            changed = True
        if req.kind is not None:
            contract.kind = req.kind
            changed = True
        if req.jurisdiction_country_code is not None:
            contract.jurisdiction_country_code = (req.jurisdiction_country_code or "").strip() or "RU"
            changed = True
        if req.governing_law_text is not None:
            contract.governing_law_text = _trim(req.governing_law_text)
            changed = True
        if req.document_id is not None:
            contract.document_id = _trim(req.document_id)
            changed = True

        if changed:
            contract.updated_at = datetime.utcnow()
            session.add(contract)
            session.commit()
            session.refresh(contract)

        return contract


class ContractPartyCreateRequest(BaseModel):
    subject_id: str
    role_key: str
    role_label: str | None = None


@router.get("/contracts/{contract_id}/parties")
def list_contract_parties(contract_id: str) -> list[ContractParty]:
    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        return list(
            session.exec(
                select(ContractParty)
                .where(ContractParty.contract_id == contract_id)
                .order_by(ContractParty.created_at.asc())
            ).all()
        )


@router.post("/contracts/{contract_id}/parties")
def create_contract_party(contract_id: str, req: ContractPartyCreateRequest) -> ContractParty:
    role_key = (req.role_key or "").strip()
    if not role_key:
        raise HTTPException(status_code=400, detail="role_key is required")

    party = ContractParty(
        contract_id=contract_id,
        subject_id=req.subject_id,
        role_key=role_key,
        role_label=_trim(req.role_label),
    )

    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        if not session.get(LegalSubject, req.subject_id):
            raise HTTPException(status_code=404, detail="subject_id not found")

        session.add(party)
        session.commit()
        session.refresh(party)
        return party


class ContractObjectCreateRequest(BaseModel):
    kind: str
    title: str
    description: str | None = None
    address: str | None = None


@router.get("/contracts/{contract_id}/objects")
def list_contract_objects(contract_id: str) -> list[ContractObject]:
    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        return list(
            session.exec(
                select(ContractObject)
                .where(ContractObject.contract_id == contract_id)
                .order_by(ContractObject.created_at.asc())
            ).all()
        )


@router.post("/contracts/{contract_id}/objects")
def create_contract_object(contract_id: str, req: ContractObjectCreateRequest) -> ContractObject:
    kind = (req.kind or "").strip()
    title = (req.title or "").strip()
    if not kind:
        raise HTTPException(status_code=400, detail="kind is required")
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    obj = ContractObject(
        contract_id=contract_id,
        kind=kind,
        title=title,
        description=_trim(req.description),
        address=_trim(req.address),
    )

    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj


class ContractEventCreateRequest(BaseModel):
    kind: str
    title: str
    start_date: date_type | None = None
    end_date: date_type | None = None


@router.get("/contracts/{contract_id}/events")
def list_contract_events(contract_id: str) -> list[ContractEvent]:
    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        return list(
            session.exec(
                select(ContractEvent)
                .where(ContractEvent.contract_id == contract_id)
                .order_by(ContractEvent.created_at.asc())
            ).all()
        )


@router.post("/contracts/{contract_id}/events")
def create_contract_event(contract_id: str, req: ContractEventCreateRequest) -> ContractEvent:
    kind = (req.kind or "").strip()
    title = (req.title or "").strip()
    if not kind:
        raise HTTPException(status_code=400, detail="kind is required")
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    ev = ContractEvent(
        contract_id=contract_id,
        kind=kind,
        title=title,
        start_date=req.start_date,
        end_date=req.end_date,
    )

    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        session.add(ev)
        session.commit()
        session.refresh(ev)
        return ev


class ContractConditionCreateRequest(BaseModel):
    kind: str
    expression: str


@router.get("/contracts/{contract_id}/conditions")
def list_contract_conditions(contract_id: str) -> list[ContractCondition]:
    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        return list(
            session.exec(
                select(ContractCondition)
                .where(ContractCondition.contract_id == contract_id)
                .order_by(ContractCondition.created_at.asc())
            ).all()
        )


@router.post("/contracts/{contract_id}/conditions")
def create_contract_condition(contract_id: str, req: ContractConditionCreateRequest) -> ContractCondition:
    kind = (req.kind or "").strip()
    expression = (req.expression or "").strip()
    if not kind:
        raise HTTPException(status_code=400, detail="kind is required")
    if not expression:
        raise HTTPException(status_code=400, detail="expression is required")

    cond = ContractCondition(contract_id=contract_id, kind=kind, expression=expression)

    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        session.add(cond)
        session.commit()
        session.refresh(cond)
        return cond


class NormativeStatementCreateRequest(BaseModel):
    kind: NormativeStatementKind
    actor_party_id: str
    counterparty_party_id: str | None = None
    object_id: str | None = None
    action_verb: str | None = None
    description: str
    condition_id: str | None = None
    due_event_id: str | None = None
    due_date: date_type | None = None


@router.get("/contracts/{contract_id}/statements")
def list_normative_statements(contract_id: str) -> list[NormativeStatement]:
    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        return list(
            session.exec(
                select(NormativeStatement)
                .where(NormativeStatement.contract_id == contract_id)
                .order_by(NormativeStatement.created_at.asc())
            ).all()
        )


@router.post("/contracts/{contract_id}/statements")
def create_normative_statement(contract_id: str, req: NormativeStatementCreateRequest) -> NormativeStatement:
    description = (req.description or "").strip()
    if not description:
        raise HTTPException(status_code=400, detail="description is required")

    stmt = NormativeStatement(
        contract_id=contract_id,
        kind=req.kind,
        actor_party_id=req.actor_party_id,
        counterparty_party_id=_trim(req.counterparty_party_id),
        object_id=_trim(req.object_id),
        action_verb=_trim(req.action_verb),
        description=description,
        condition_id=_trim(req.condition_id),
        due_event_id=_trim(req.due_event_id),
        due_date=req.due_date,
    )

    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        if not session.get(ContractParty, req.actor_party_id):
            raise HTTPException(status_code=404, detail="actor_party_id not found")
        if req.counterparty_party_id and not session.get(ContractParty, req.counterparty_party_id):
            raise HTTPException(status_code=404, detail="counterparty_party_id not found")
        if req.object_id and not session.get(ContractObject, req.object_id):
            raise HTTPException(status_code=404, detail="object_id not found")
        if req.condition_id and not session.get(ContractCondition, req.condition_id):
            raise HTTPException(status_code=404, detail="condition_id not found")
        if req.due_event_id and not session.get(ContractEvent, req.due_event_id):
            raise HTTPException(status_code=404, detail="due_event_id not found")

        session.add(stmt)
        session.commit()
        session.refresh(stmt)
        return stmt


class PaymentTermCreateRequest(BaseModel):
    payer_party_id: str
    payee_party_id: str
    kind: PaymentTermKind
    amount_minor: int | None = None
    currency_code: str | None = "RUB"
    percent: float | None = None
    due_event_id: str | None = None
    due_date: date_type | None = None
    description: str | None = None


@router.get("/contracts/{contract_id}/payment-terms")
def list_payment_terms(contract_id: str) -> list[PaymentTerm]:
    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        return list(
            session.exec(
                select(PaymentTerm)
                .where(PaymentTerm.contract_id == contract_id)
                .order_by(PaymentTerm.created_at.asc())
            ).all()
        )


@router.post("/contracts/{contract_id}/payment-terms")
def create_payment_term(contract_id: str, req: PaymentTermCreateRequest) -> PaymentTerm:
    pt = PaymentTerm(
        contract_id=contract_id,
        payer_party_id=req.payer_party_id,
        payee_party_id=req.payee_party_id,
        kind=req.kind,
        amount_minor=req.amount_minor,
        currency_code=(req.currency_code or "RUB").strip() or "RUB",
        percent=req.percent,
        due_event_id=_trim(req.due_event_id),
        due_date=req.due_date,
        description=_trim(req.description),
    )

    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        if not session.get(ContractParty, req.payer_party_id):
            raise HTTPException(status_code=404, detail="payer_party_id not found")
        if not session.get(ContractParty, req.payee_party_id):
            raise HTTPException(status_code=404, detail="payee_party_id not found")
        if req.due_event_id and not session.get(ContractEvent, req.due_event_id):
            raise HTTPException(status_code=404, detail="due_event_id not found")

        session.add(pt)
        session.commit()
        session.refresh(pt)
        return pt


class ContractClauseCreateRequest(BaseModel):
    kind: str
    title: str | None = None
    body: str | None = None
    data: dict | None = None


@router.get("/contracts/{contract_id}/clauses")
def list_contract_clauses(contract_id: str) -> list[ContractClause]:
    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        return list(
            session.exec(
                select(ContractClause)
                .where(ContractClause.contract_id == contract_id)
                .order_by(ContractClause.created_at.asc())
            ).all()
        )


@router.post("/contracts/{contract_id}/clauses")
def create_contract_clause(contract_id: str, req: ContractClauseCreateRequest) -> ContractClause:
    kind = (req.kind or "").strip()
    if not kind:
        raise HTTPException(status_code=400, detail="kind is required")

    clause = ContractClause(
        contract_id=contract_id,
        kind=kind,
        title=_trim(req.title),
        body=req.body,
        data=req.data,
    )

    with get_session() as session:
        if not session.get(Contract, contract_id):
            raise HTTPException(status_code=404, detail="Contract not found")
        session.add(clause)
        session.commit()
        session.refresh(clause)
        return clause


class LegalNormCreateRequest(BaseModel):
    jurisdiction_country_code: str | None = "RU"
    citation: str
    url: str | None = None


@router.get("/legal-norms")
def list_legal_norms() -> list[LegalNormReference]:
    with get_session() as session:
        return list(
            session.exec(select(LegalNormReference).order_by(LegalNormReference.created_at.desc())).all()
        )


@router.post("/legal-norms")
def create_legal_norm(req: LegalNormCreateRequest) -> LegalNormReference:
    citation = (req.citation or "").strip()
    if not citation:
        raise HTTPException(status_code=400, detail="citation is required")

    norm = LegalNormReference(
        jurisdiction_country_code=(req.jurisdiction_country_code or "RU").strip() or "RU",
        citation=citation,
        url=_trim(req.url),
    )

    with get_session() as session:
        session.add(norm)
        session.commit()
        session.refresh(norm)
        return norm


class LinkNormRequest(BaseModel):
    norm_id: str


@router.post("/clauses/{clause_id}/norms")
def link_norm_to_clause(clause_id: str, req: LinkNormRequest) -> ClauseNormLink:
    with get_session() as session:
        clause = session.get(ContractClause, clause_id)
        if not clause:
            raise HTTPException(status_code=404, detail="Clause not found")
        norm = session.get(LegalNormReference, req.norm_id)
        if not norm:
            raise HTTPException(status_code=404, detail="Norm not found")

        existing = session.exec(
            select(ClauseNormLink)
            .where(ClauseNormLink.clause_id == clause_id)
            .where(ClauseNormLink.norm_id == req.norm_id)
            .limit(1)
        ).first()
        if existing:
            return existing

        link = ClauseNormLink(clause_id=clause_id, norm_id=req.norm_id)
        session.add(link)
        session.commit()
        session.refresh(link)
        return link


@router.post("/statements/{statement_id}/norms")
def link_norm_to_statement(statement_id: str, req: LinkNormRequest) -> StatementNormLink:
    with get_session() as session:
        stmt = session.get(NormativeStatement, statement_id)
        if not stmt:
            raise HTTPException(status_code=404, detail="Statement not found")
        norm = session.get(LegalNormReference, req.norm_id)
        if not norm:
            raise HTTPException(status_code=404, detail="Norm not found")

        existing = session.exec(
            select(StatementNormLink)
            .where(StatementNormLink.statement_id == statement_id)
            .where(StatementNormLink.norm_id == req.norm_id)
            .limit(1)
        ).first()
        if existing:
            return existing

        link = StatementNormLink(statement_id=statement_id, norm_id=req.norm_id)
        session.add(link)
        session.commit()
        session.refresh(link)
        return link
