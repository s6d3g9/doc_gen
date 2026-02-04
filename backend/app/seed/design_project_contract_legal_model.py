from __future__ import annotations

from datetime import date
from datetime import datetime

from sqlmodel import select

from ..artifacts import write_text
from ..db import get_session
from ..models import (
    Contract,
    ContractClause,
    ContractCondition,
    ContractEvent,
    ContractKind,
    ContractObject,
    ContractParty,
    LegalNormReference,
    LegalSubject,
    LegalSubjectKind,
    NormativeStatement,
    NormativeStatementKind,
    PaymentTerm,
    PaymentTermKind,
    Document,
    DocumentVersion,
)

SEED_MARKER_TITLE = "Договор на разработку дизайн‑проекта (legal model sample)"


SAMPLE_DOCUMENT_TITLE = "Договор на разработку дизайн‑проекта (sample document)"


def _seed_document_for_contract(*, session, contract: Contract) -> tuple[Document, DocumentVersion]:
    """Create a sample Document + Version and attach to Contract."""

    doc = Document(title=SAMPLE_DOCUMENT_TITLE)
    text = (
        "ДОГОВОР (пример)\n"
        "на разработку дизайн‑проекта\n\n"
        "1. СТОРОНЫ\n"
        "{{customer.requisites}}\n\n"
        "{{executor.requisites}}\n\n"
        "2. ОБЪЕКТ\n"
        "{{object.address.line}}\n\n"
        "Этот документ создан seed-скриптом для демонстрации связи:\n"
        "Contract → Document → DocumentVersion (artifact).\n"
    )
    artifact_path = write_text(text, suffix=".txt")
    version = DocumentVersion(
        document_id=doc.id,
        artifact_path=artifact_path,
        content_type="text/plain",
    )

    session.add(doc)
    session.add(version)
    session.commit()
    session.refresh(doc)
    session.refresh(version)

    contract.document_id = doc.id
    contract.updated_at = datetime.utcnow()
    session.add(contract)
    session.commit()
    session.refresh(contract)

    return doc, version


def seed() -> dict[str, str]:
    """Seeds a minimal but representative RU-first legal domain model example.

    Creates:
    - LegalSubject (executor org placeholder, customer person)
    - Contract + Parties
    - ContractObject (design project)
    - Events (start/end/acceptance)
    - Conditions
    - NormativeStatements (subject-action-object)
    - PaymentTerm
    - Clauses
    - LegalNormReference + links are intentionally left for manual demo

    Returns ids for quick use.
    """

    with get_session() as session:
        existing = session.exec(
            select(Contract).where(Contract.title == SEED_MARKER_TITLE).limit(1)
        ).first()
        if existing:
            out: dict[str, str] = {"contract_id": existing.id}

            # Ensure the sample contract is linked to a Document.
            if not existing.document_id:
                doc, ver = _seed_document_for_contract(session=session, contract=existing)
                out["document_id"] = doc.id
                out["version_id"] = ver.id
            else:
                out["document_id"] = existing.document_id
            return out

        executor = LegalSubject(
            kind=LegalSubjectKind.organization,
            country_code="RU",
            display_name="ООО \"Пример Дизайн\"",
        )
        customer = LegalSubject(
            kind=LegalSubjectKind.person,
            country_code="RU",
            display_name="Иванов Иван Иванович",
            first_name="Иван",
            last_name="Иванов",
            middle_name="Иванович",
        )

        session.add(executor)
        session.add(customer)
        session.commit()
        session.refresh(executor)
        session.refresh(customer)

        contract = Contract(
            title=SEED_MARKER_TITLE,
            kind=ContractKind.works,
            jurisdiction_country_code="RU",
            governing_law_text="Российская Федерация (ГК РФ)",
            document_id=None,
        )
        session.add(contract)
        session.commit()
        session.refresh(contract)

        party_executor = ContractParty(
            contract_id=contract.id,
            subject_id=executor.id,
            role_key="executor",
            role_label="Исполнитель",
        )
        party_customer = ContractParty(
            contract_id=contract.id,
            subject_id=customer.id,
            role_key="customer",
            role_label="Заказчик",
        )
        session.add(party_executor)
        session.add(party_customer)
        session.commit()
        session.refresh(party_executor)
        session.refresh(party_customer)

        obj = ContractObject(
            contract_id=contract.id,
            kind="work_result",
            title="Дизайн‑проект (результат работ)",
            description="Комплект материалов: планировки, коллажи, 3D, чертежи, спецификации",
            address="г. Москва, ул. Примерная, д. 1, кв. 1",
        )
        session.add(obj)
        session.commit()
        session.refresh(obj)

        ev_start = ContractEvent(
            contract_id=contract.id,
            kind="work_start",
            title="Начало работ",
            start_date=date(2026, 2, 10),
            end_date=None,
        )
        ev_end = ContractEvent(
            contract_id=contract.id,
            kind="work_end",
            title="Окончание работ",
            start_date=date(2026, 3, 20),
            end_date=None,
        )
        ev_accept = ContractEvent(
            contract_id=contract.id,
            kind="acceptance_deadline",
            title="Срок приемки результата",
            start_date=None,
            end_date=None,
        )
        session.add(ev_start)
        session.add(ev_end)
        session.add(ev_accept)
        session.commit()
        session.refresh(ev_start)
        session.refresh(ev_end)
        session.refresh(ev_accept)

        cond_customer_inputs = ContractCondition(
            contract_id=contract.id,
            kind="customer_inputs_provided",
            expression="Заказчик предоставил исходные данные (ТЗ/планировки/фото/замеры)",
        )
        session.add(cond_customer_inputs)
        session.commit()
        session.refresh(cond_customer_inputs)

        # Normative statements (subject-action-object)
        st1 = NormativeStatement(
            contract_id=contract.id,
            kind=NormativeStatementKind.obligation,
            actor_party_id=party_executor.id,
            counterparty_party_id=party_customer.id,
            object_id=obj.id,
            action_verb="выполнить",
            description="Исполнитель обязуется выполнить работы по разработке дизайн‑проекта и передать результат Заказчику.",
            condition_id=cond_customer_inputs.id,
            due_event_id=ev_end.id,
            due_date=None,
        )
        st2 = NormativeStatement(
            contract_id=contract.id,
            kind=NormativeStatementKind.obligation,
            actor_party_id=party_customer.id,
            counterparty_party_id=party_executor.id,
            object_id=obj.id,
            action_verb="принять",
            description="Заказчик обязуется принять результат работ в установленном порядке.",
            condition_id=None,
            due_event_id=ev_accept.id,
            due_date=None,
        )
        st3 = NormativeStatement(
            contract_id=contract.id,
            kind=NormativeStatementKind.obligation,
            actor_party_id=party_customer.id,
            counterparty_party_id=party_executor.id,
            object_id=None,
            action_verb="оплатить",
            description="Заказчик обязуется оплатить работы на условиях договора (аванс и окончательный расчет).",
            condition_id=None,
            due_event_id=None,
            due_date=None,
        )
        session.add(st1)
        session.add(st2)
        session.add(st3)
        session.commit()
        session.refresh(st1)
        session.refresh(st2)
        session.refresh(st3)

        # Payment terms (example)
        pay1 = PaymentTerm(
            contract_id=contract.id,
            payer_party_id=party_customer.id,
            payee_party_id=party_executor.id,
            kind=PaymentTermKind.percent_of_total,
            amount_minor=None,
            currency_code="RUB",
            percent=50.0,
            due_event_id=None,
            due_date=date(2026, 2, 10),
            description="Аванс 50% до начала работ",
        )
        pay2 = PaymentTerm(
            contract_id=contract.id,
            payer_party_id=party_customer.id,
            payee_party_id=party_executor.id,
            kind=PaymentTermKind.percent_of_total,
            amount_minor=None,
            currency_code="RUB",
            percent=50.0,
            due_event_id=ev_end.id,
            due_date=None,
            description="Оставшиеся 50% после передачи результата",
        )
        session.add(pay1)
        session.add(pay2)
        session.commit()

        # Clauses (minimal set)
        clause_subject = ContractClause(
            contract_id=contract.id,
            kind="subject",
            title="Предмет договора",
            body="Исполнитель выполняет работы по разработке дизайн‑проекта, Заказчик принимает и оплачивает результат.",
            data={"object_kind": obj.kind},
        )
        clause_terms = ContractClause(
            contract_id=contract.id,
            kind="terms",
            title="Сроки",
            body="Начало и окончание работ определяются календарными датами/событиями.",
            data={"start_event_id": ev_start.id, "end_event_id": ev_end.id},
        )
        clause_acceptance = ContractClause(
            contract_id=contract.id,
            kind="acceptance",
            title="Приемка",
            body="Порядок сдачи‑приемки результата работ.",
            data={"acceptance_event_id": ev_accept.id},
        )
        clause_liability = ContractClause(
            contract_id=contract.id,
            kind="liability",
            title="Ответственность",
            body="Стороны несут ответственность в соответствии с законодательством РФ и условиями договора.",
            data={"jurisdiction": "RU"},
        )
        clause_force_majeure = ContractClause(
            contract_id=contract.id,
            kind="force_majeure",
            title="Форс‑мажор",
            body="Стороны освобождаются от ответственности при наступлении обстоятельств непреодолимой силы.",
            data=None,
        )
        session.add(clause_subject)
        session.add(clause_terms)
        session.add(clause_acceptance)
        session.add(clause_liability)
        session.add(clause_force_majeure)
        session.commit()

        # Optional: create a sample norm reference (not linked by default)
        norm = LegalNormReference(
            jurisdiction_country_code="RU",
            citation="ГК РФ (пример ссылки на норму)",
            url=None,
        )
        session.add(norm)
        session.commit()

        doc, ver = _seed_document_for_contract(session=session, contract=contract)

        return {
            "contract_id": contract.id,
            "document_id": doc.id,
            "version_id": ver.id,
            "executor_subject_id": executor.id,
            "customer_subject_id": customer.id,
            "executor_party_id": party_executor.id,
            "customer_party_id": party_customer.id,
        }


def main() -> None:
    ids = seed()
    now = datetime.utcnow().isoformat()
    print("seeded: design_project_contract_legal_model")
    for k, v in ids.items():
        print(f"{k}: {v}")
    print(f"utc: {now}")


if __name__ == "__main__":
    main()
