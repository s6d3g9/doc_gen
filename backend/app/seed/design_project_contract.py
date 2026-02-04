from __future__ import annotations

from datetime import datetime

from sqlmodel import select

from ..db import get_session
from ..models import DocumentTemplate, DocumentTemplateField, DocumentTemplateVersion, TemplateFieldType

TEMPLATE_TITLE = "Договор на разработку дизайн‑проекта"
TEMPLATE_CATEGORY = "contracts"
TEMPLATE_DESCRIPTION = "Шаблон договора на разработку дизайн‑проекта (базовый пример)"


TEMPLATE_BODY_V1 = """ДОГОВОР № {{ contract_number }}
на разработку дизайн‑проекта

г. {{ city }}\n{{ contract_date }}

{{ executor_org_id_name }} (ИНН: {{ executor_org_id_inn }}{% if executor_org_id_ogrn is defined %}, ОГРН: {{ executor_org_id_ogrn }}{% endif %}),
адрес: {{ executor_org_id_address }},
именуемое далее «Исполнитель», в лице уполномоченного представителя,
и {{ customer_name }}, именуемый(ая) далее «Заказчик»,
совместно именуемые «Стороны», заключили настоящий договор (далее — «Договор») о нижеследующем.

1. ПРЕДМЕТ ДОГОВОРА
1.1. Исполнитель обязуется выполнить работы по разработке дизайн‑проекта для объекта по адресу: {{ object_address }} (далее — «Объект»),
а Заказчик обязуется принять результат работ и оплатить его на условиях настоящего Договора.
1.2. Наименование проекта: {{ project_title }}.
1.3. Состав результата работ (пакет дизайн‑проекта): {{ deliverables }}.

2. СРОКИ ВЫПОЛНЕНИЯ РАБОТ
2.1. Начало работ: {{ start_date }}.
2.2. Окончание работ: {{ end_date }}.
2.3. Сроки могут корректироваться по соглашению Сторон, в том числе при задержке предоставления исходных данных Заказчиком.

3. СТОИМОСТЬ И ПОРЯДОК ОПЛАТЫ
3.1. Стоимость работ по Договору составляет: {{ price_total }}.
3.2. Аванс: {{ prepayment_percent }}% от стоимости работ.
3.3. Оплата производится по выставленным счетам/реквизитам Исполнителя. Способ оплаты: {{ payment_method }}.

4. ПРАВА И ОБЯЗАННОСТИ СТОРОН
4.1. Исполнитель обязуется:
  4.1.1. Выполнить работы качественно и в сроки, предусмотренные Договором.
  4.1.2. Предоставлять Заказчику промежуточные материалы для согласования при необходимости.
4.2. Заказчик обязуется:
  4.2.1. Предоставить исходные данные (планировки, ТЗ, фото/замеры) в срок: {{ input_deadline }}.
  4.2.2. Согласовывать предоставленные материалы в разумный срок.
  4.2.3. Оплатить работы в порядке и сроки, предусмотренные Договором.

5. ПРИЕМКА РЕЗУЛЬТАТА
5.1. Результат работ передается Заказчику в формате: {{ delivery_format }}.
5.2. Заказчик принимает результат работ путем подписания акта/подтверждения по электронной почте в течение {{ acceptance_days }} дней.
5.3. При наличии замечаний Заказчик направляет их Исполнителю в письменной форме в пределах срока приемки.

6. ОТВЕТСТВЕННОСТЬ СТОРОН
6.1. Стороны несут ответственность в соответствии с законодательством РФ и условиями Договора.
6.2. Исполнитель не несет ответственности за решения и действия третьих лиц (подрядчиков, поставщиков), если иное не согласовано Сторонами.

7. ФОРС‑МАЖОР
7.1. Стороны освобождаются от ответственности за частичное или полное неисполнение обязательств при наступлении обстоятельств непреодолимой силы.

8. ПРОЧИЕ УСЛОВИЯ
8.1. Переписка по email считается надлежащей, если ведется с адресов: {{ customer_email }} / {{ executor_org_id_email }}.
8.2. Настоящий Договор составлен в электронном виде; по запросу может быть оформлен на бумаге.

9. РЕКВИЗИТЫ СТОРОН

ИСПОЛНИТЕЛЬ:\n{{ executor_org_id_name }}\nИНН: {{ executor_org_id_inn }}\n{% if executor_org_id_kpp is defined %}КПП: {{ executor_org_id_kpp }}\n{% endif %}Адрес: {{ executor_org_id_address }}\n{% if executor_org_id_phone is defined %}Тел.: {{ executor_org_id_phone }}\n{% endif %}{% if executor_org_id_email is defined %}Email: {{ executor_org_id_email }}\n{% endif %}

ЗАКАЗЧИК:\n{{ customer_name }}\nТел.: {{ customer_phone }}\nEmail: {{ customer_email }}\n
Подписи:\n\n_____________________ / Исполнитель /\n\n_____________________ / Заказчик /\n"""


TEMPLATE_BODY_V2 = """ДОГОВОР № {{ contract_number }}
на разработку дизайн‑проекта

г. {{ city }}\n{{ contract_date }}

{{ executor_org_id_name }}{% if executor_org_id_inn is defined %} (ИНН: {{ executor_org_id_inn }}{% if executor_org_id_ogrn is defined %}, ОГРН: {{ executor_org_id_ogrn }}{% endif %}){% endif %}
{% if executor_org_id_address is defined %}адрес: {{ executor_org_id_address }}{% endif %}
именуемое далее «Исполнитель»,
и {{ customer_name }}, именуемый(ая) далее «Заказчик»,
совместно именуемые «Стороны», заключили настоящий договор (далее — «Договор») о нижеследующем.

1. ПРЕДМЕТ ДОГОВОРА
1.1. Исполнитель обязуется выполнить работы по разработке дизайн‑проекта для объекта по адресу: {{ object_address }} (далее — «Объект»),
а Заказчик обязуется принять результат работ и оплатить его на условиях настоящего Договора.
1.2. Наименование проекта: {{ project_title }}.
{% if deliverables %}1.3. Состав результата работ (пакет дизайн‑проекта): {{ deliverables }}.{% endif %}

2. СРОКИ ВЫПОЛНЕНИЯ РАБОТ
2.1. Начало работ: {{ start_date }}.
2.2. Окончание работ: {{ end_date }}.
2.3. Сроки могут корректироваться по соглашению Сторон, в том числе при задержке предоставления исходных данных Заказчиком.

3. СТОИМОСТЬ И ПОРЯДОК ОПЛАТЫ
3.1. Стоимость работ по Договору составляет: {{ price_total }}.
3.2. Аванс: {{ prepayment_percent }}% от стоимости работ.
{% if payment_method %}3.3. Способ оплаты: {{ payment_method }}.{% endif %}

4. ПРАВА И ОБЯЗАННОСТИ СТОРОН
4.1. Исполнитель обязуется выполнить работы качественно и в сроки, предусмотренные Договором.
4.2. Заказчик обязуется предоставить исходные данные в срок: {{ input_deadline }} и своевременно согласовывать материалы.

5. ПРИЕМКА РЕЗУЛЬТАТА
5.1. Результат работ передается Заказчику в формате: {{ delivery_format }}.
5.2. Заказчик принимает результат работ в течение {{ acceptance_days }} дней.

6. ПРОЧИЕ УСЛОВИЯ
6.1. Переписка по email считается надлежащей, если ведется с адресов:
{% if customer_email %}- Заказчик: {{ customer_email }}{% endif %}
{% if executor_org_id_email is defined %}- Исполнитель: {{ executor_org_id_email }}{% endif %}

7. РЕКВИЗИТЫ СТОРОН

ИСПОЛНИТЕЛЬ:\n{{ executor_org_id_name }}\n{% if executor_org_id_inn is defined %}ИНН: {{ executor_org_id_inn }}\n{% endif %}{% if executor_org_id_kpp is defined %}КПП: {{ executor_org_id_kpp }}\n{% endif %}{% if executor_org_id_address is defined %}Адрес: {{ executor_org_id_address }}\n{% endif %}{% if executor_org_id_phone is defined %}Тел.: {{ executor_org_id_phone }}\n{% endif %}{% if executor_org_id_email is defined %}Email: {{ executor_org_id_email }}\n{% endif %}

ЗАКАЗЧИК:\n{{ customer_name }}\n{% if customer_phone %}Тел.: {{ customer_phone }}\n{% endif %}{% if customer_email %}Email: {{ customer_email }}\n{% endif %}

Подписи:\n\n_____________________ / Исполнитель /\n\n_____________________ / Заказчик /\n"""


FIELDS_V1: list[tuple[str, str, TemplateFieldType, bool, int]] = [
    ("contract_number", "Номер договора", TemplateFieldType.text, True, 10),
    ("contract_date", "Дата договора", TemplateFieldType.date, True, 20),
    ("city", "Город", TemplateFieldType.text, True, 30),
    ("executor_org_id", "Исполнитель (организация)", TemplateFieldType.organization_ref, True, 40),
    ("customer_name", "Заказчик (ФИО/наименование)", TemplateFieldType.text, True, 50),
    ("customer_phone", "Телефон заказчика", TemplateFieldType.text, True, 60),
    ("customer_email", "Email заказчика", TemplateFieldType.text, True, 70),
    ("project_title", "Название проекта", TemplateFieldType.text, True, 80),
    ("object_address", "Адрес объекта", TemplateFieldType.text, True, 90),
    ("deliverables", "Состав дизайн‑проекта", TemplateFieldType.text, True, 100),
    ("start_date", "Дата начала работ", TemplateFieldType.date, True, 110),
    ("end_date", "Дата окончания работ", TemplateFieldType.date, True, 120),
    ("price_total", "Стоимость работ", TemplateFieldType.text, True, 130),
    ("prepayment_percent", "Аванс (%)", TemplateFieldType.number, True, 140),
    ("payment_method", "Способ оплаты", TemplateFieldType.text, True, 150),
    ("input_deadline", "Срок предоставления исходных данных", TemplateFieldType.text, True, 160),
    ("delivery_format", "Формат передачи результата", TemplateFieldType.text, True, 170),
    ("acceptance_days", "Срок приемки (дней)", TemplateFieldType.number, True, 180),
]


FIELDS_V2: list[tuple[str, str, TemplateFieldType, bool, int]] = [
    ("contract_number", "Номер договора", TemplateFieldType.text, True, 10),
    ("contract_date", "Дата договора", TemplateFieldType.date, True, 20),
    ("city", "Город", TemplateFieldType.text, True, 30),
    ("executor_org_id", "Исполнитель (организация)", TemplateFieldType.organization_ref, True, 40),
    ("customer_name", "Заказчик (ФИО/наименование)", TemplateFieldType.text, True, 50),
    ("customer_phone", "Телефон заказчика", TemplateFieldType.text, False, 60),
    ("customer_email", "Email заказчика", TemplateFieldType.text, False, 70),
    ("project_title", "Название проекта", TemplateFieldType.text, True, 80),
    ("object_address", "Адрес объекта", TemplateFieldType.text, True, 90),
    ("deliverables", "Состав дизайн‑проекта", TemplateFieldType.text, False, 100),
    ("start_date", "Дата начала работ", TemplateFieldType.date, True, 110),
    ("end_date", "Дата окончания работ", TemplateFieldType.date, True, 120),
    ("price_total", "Стоимость работ", TemplateFieldType.text, True, 130),
    ("prepayment_percent", "Аванс (%)", TemplateFieldType.number, True, 140),
    ("payment_method", "Способ оплаты", TemplateFieldType.text, False, 150),
    ("input_deadline", "Срок предоставления исходных данных", TemplateFieldType.text, True, 160),
    ("delivery_format", "Формат передачи результата", TemplateFieldType.text, True, 170),
    ("acceptance_days", "Срок приемки (дней)", TemplateFieldType.number, True, 180),
]


def seed() -> str:
    """Create the sample template if missing.

    Returns the template_version_id (latest).
    """

    with get_session() as session:
        tpl = session.exec(
            select(DocumentTemplate)
            .where(DocumentTemplate.title == TEMPLATE_TITLE)
            .limit(1)
        ).first()
        if not tpl:
            tpl = DocumentTemplate(title=TEMPLATE_TITLE, category=TEMPLATE_CATEGORY, description=TEMPLATE_DESCRIPTION)
            session.add(tpl)
            session.commit()
            session.refresh(tpl)

        v1 = session.exec(
            select(DocumentTemplateVersion)
            .where(DocumentTemplateVersion.template_id == tpl.id)
            .where(DocumentTemplateVersion.version == 1)
            .limit(1)
        ).first()
        if not v1:
            v1 = DocumentTemplateVersion(template_id=tpl.id, version=1, body=TEMPLATE_BODY_V1)
            session.add(v1)
            session.commit()
            session.refresh(v1)

            for key, label, field_type, required, order in FIELDS_V1:
                session.add(
                    DocumentTemplateField(
                        template_version_id=v1.id,
                        key=key,
                        label=label,
                        field_type=field_type,
                        required=required,
                        order=order,
                    )
                )
            session.commit()

        v2 = session.exec(
            select(DocumentTemplateVersion)
            .where(DocumentTemplateVersion.template_id == tpl.id)
            .where(DocumentTemplateVersion.version == 2)
            .limit(1)
        ).first()
        if not v2:
            v2 = DocumentTemplateVersion(template_id=tpl.id, version=2, body=TEMPLATE_BODY_V2)
            session.add(v2)
            session.commit()
            session.refresh(v2)

            for key, label, field_type, required, order in FIELDS_V2:
                session.add(
                    DocumentTemplateField(
                        template_version_id=v2.id,
                        key=key,
                        label=label,
                        field_type=field_type,
                        required=required,
                        order=order,
                    )
                )
            session.commit()

        return v2.id


def main() -> None:
    tv_id = seed()
    now = datetime.utcnow().isoformat()
    print(f"seeded: {TEMPLATE_TITLE}")
    print(f"template_version_id: {tv_id}")
    print(f"utc: {now}")


if __name__ == "__main__":
    main()
