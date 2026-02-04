import React from 'react'
import {
  addVersionFromFile,
  addVersionFromText,
  aiChat,
  aiExtractEntities,
  aiGenerateTemplate,
  createDocumentFromFile,
  createDocumentFromText,
  createOpenRouterKey,
  DocumentIndexItem,
  DocumentType,
  DocumentVersion,
  downloadVersionArtifactBlob,
  fetchVersionArtifactText,
  getOpenRouterConfig,
  listDocumentTypes,
  listDocumentsIndex,
  listDocumentVersions,
  listOpenRouterKeys,
  listOpenRouterModels,
  saveToGoogleDocs,
  setOpenRouterActive,
  type AIChatMessage,
  type OpenRouterKey,
  type OpenRouterModel,
} from '../api'
import { usePropertiesSlot } from '../layout/PropertiesSlot'

type Selection = {
  doc: DocumentIndexItem
  versions: DocumentVersion[]
}

type TypeFilter =
  | { mode: 'all' }
  | { mode: 'type'; typeId: string }
  | { mode: 'untyped' }

type DocumentsScreenProps = {
  isAuthed: boolean
}

type EntityFields = {
  customer_status: 'person' | 'ip' | 'self_employed' | 'company'
  customer_fio: string
  customer_address: string
  customer_phone: string
  customer_email: string
  customer_inn: string
  customer_telegram: string
  customer_whatsapp: string

  executor_name: string
  executor_address: string
  executor_inn: string
  executor_phone: string
  executor_email: string
  executor_telegram: string

  object_address: string
  object_type: 'apartment' | 'house' | 'commercial' | 'other'
  object_rooms_count: string
  object_area_sqm: string
  object_ceiling_height_m: string
  object_floor: string
  object_floors_total: string
  object_bathrooms_count: string
  object_has_balcony: 'no' | 'yes'
  object_rooms_list: string
  object_residents_count: string
  object_has_pets: 'no' | 'yes'
  object_pets_notes: string

  project_scope: 'full' | 'rooms_only' | 'consultation' | 'other'
  project_style: string
  project_renovation_type: 'new_build' | 'secondary' | 'cosmetic' | 'capital' | 'other'
  project_budget: string
  project_deadline: string
  project_notes: string

  // Legacy free-form price field (kept for backwards compatibility with older AI outputs/templates).
  project_price: string

  // Preferred structured pricing fields.
  project_price_per_sqm: string
  project_price_total: string
  project_payment_terms: string
  payment_method_cash: boolean
  payment_method_bank_transfer: boolean
  payment_method_card: boolean
  payment_method_sbp: boolean
  payment_method_other: string
  project_revisions_included: string
  project_revision_extra_terms: string
  project_author_supervision: 'no' | 'yes'
  project_site_visits_count: string
  project_site_visits_paid_by: 'customer' | 'executor' | 'split' | 'other'
  project_site_visits_paid_by_details: string
  project_site_visits_expenses: string

  project_procurement_buys_paid_by: 'customer' | 'executor' | 'split' | 'other'
  project_procurement_buys_details: string
  project_procurement_delivery_acceptance_by: 'customer' | 'executor' | 'split' | 'other'
  project_procurement_delivery_acceptance_details: string
  project_procurement_lifting_assembly_paid_by: 'customer' | 'executor' | 'split' | 'other'
  project_procurement_lifting_assembly_details: string
  project_procurement_storage_paid_by: 'customer' | 'executor' | 'split' | 'other'
  project_procurement_storage_details: string

  project_approval_sla: string
  project_deadline_shift_terms: string
  project_penalties_terms: string
  project_handover_format: string
  project_communication_channel: 'telegram' | 'whatsapp' | 'email' | 'phone' | 'other'
  project_communication_details: string
  project_communication_rules: string

  deliverable_measurements: boolean
  deliverable_plan_solution: boolean
  deliverable_demolition_plan: boolean
  deliverable_construction_plan: boolean
  deliverable_electric_plan: boolean
  deliverable_plumbing_plan: boolean
  deliverable_lighting_plan: boolean
  deliverable_ceiling_plan: boolean
  deliverable_floor_plan: boolean
  deliverable_furniture_plan: boolean
  deliverable_finishes_schedule: boolean
  deliverable_specification: boolean
  deliverable_3d_visuals: boolean
}

function normalizeSpaces(s: string) {
  return String(s || '').replace(/\s+/g, ' ').trim()
}

function formatFioShort(fio: string) {
  const norm = normalizeSpaces(fio)
  if (!norm) return ''
  const parts = norm.split(' ').filter(Boolean)
  if (parts.length === 1) return parts[0]
  const last = parts[0]
  const first = parts[1]
  const middle = parts[2]
  const fi = first ? `${first[0]}.` : ''
  const mi = middle ? `${middle[0]}.` : ''
  return normalizeSpaces(`${last} ${fi}${mi}`)
}

function formatPhone(phone: string) {
  const digits = String(phone || '').replace(/\D+/g, '')
  if (!digits) return ''

  // RU-friendly: 8XXXXXXXXXX or 7XXXXXXXXXX -> +7 (XXX) XXX-XX-XX
  const normalized = digits.length === 11 && (digits.startsWith('8') || digits.startsWith('7'))
    ? `7${digits.slice(1)}`
    : digits

  if (normalized.length === 11 && normalized.startsWith('7')) {
    const a = normalized.slice(1, 4)
    const b = normalized.slice(4, 7)
    const c = normalized.slice(7, 9)
    const d = normalized.slice(9, 11)
    return `+7 (${a}) ${b}-${c}-${d}`
  }

  return phone.trim()
}

function formatEmail(email: string) {
  const norm = normalizeSpaces(email)
  return norm ? norm.toLowerCase() : ''
}

function formatTelegram(handle: string) {
  const norm = normalizeSpaces(handle)
  if (!norm) return ''
  if (norm.startsWith('@')) return norm
  // allow t.me links too
  if (norm.startsWith('http://') || norm.startsWith('https://')) return norm
  return `@${norm}`
}

function formatWhatsapp(value: string) {
  // accept either a phone number or a URL
  const norm = normalizeSpaces(value)
  if (!norm) return ''
  if (norm.startsWith('http://') || norm.startsWith('https://')) return norm
  return formatPhone(norm) || norm
}

function formatObjectTypeLabel(t: EntityFields['object_type']) {
  switch (t) {
    case 'apartment':
      return 'Квартира'
    case 'house':
      return 'Дом'
    case 'commercial':
      return 'Коммерческий объект'
    case 'other':
      return 'Другое'
    default:
      return ''
  }
}

function formatProjectScopeLabel(s: EntityFields['project_scope']) {
  switch (s) {
    case 'full':
      return 'Дизайн‑проект под ключ'
    case 'rooms_only':
      return 'Отдельные помещения'
    case 'consultation':
      return 'Консультация'
    case 'other':
      return 'Другое'
    default:
      return ''
  }
}

function formatRenovationTypeLabel(r: EntityFields['project_renovation_type']) {
  switch (r) {
    case 'new_build':
      return 'Новостройка'
    case 'secondary':
      return 'Вторичка'
    case 'cosmetic':
      return 'Косметический ремонт'
    case 'capital':
      return 'Капитальный ремонт'
    case 'other':
      return 'Другое'
    default:
      return ''
  }
}

function normalizeNumericString(value: string) {
  const s = normalizeSpaces(value)
  if (!s) return ''
  // Keep digits, dot/comma and minus; replace comma with dot
  const cleaned = s.replace(/[^0-9,.-]+/g, '').replace(',', '.')
  return cleaned
}

function parseNumber(value: string): number | null {
  const cleaned = normalizeNumericString(value)
  if (!cleaned) return null
  const n = Number(cleaned)
  return Number.isFinite(n) ? n : null
}

function formatRub(amount: number): string {
  const rounded = Math.round(amount)
  return `${new Intl.NumberFormat('ru-RU').format(rounded)} ₽`
}

function parsePricePerSqm(raw: string): number | null {
  const s = normalizeSpaces(raw).toLowerCase()
  if (!s) return null

  // Heuristic: treat as "per m²" when the string clearly indicates that.
  const perSqm = /(?:\/\s*м\s*(?:2|²)|за\s*м\s*(?:2|²)|на\s*м\s*(?:2|²))/i.test(s)
  if (!perSqm) return null

  // Extract the first number-like token as the rate.
  const m = s.match(/[-+]?\d[\d\s.,]*/)
  if (!m) return null
  return parseNumber(m[0])
}

function parseRatePerSqm(f: EntityFields): number | null {
  const direct = parseNumber(f.project_price_per_sqm)
  if (direct != null) return direct
  return parsePricePerSqm(f.project_price)
}

function computedProjectPrice(f: EntityFields): { rate: number; area: number; total: number } | null {
  const rate = parseRatePerSqm(f)
  if (rate == null) return null
  const area = parseNumber(f.object_area_sqm)
  if (area == null) return null
  const total = rate * area
  if (!Number.isFinite(total) || total <= 0) return null
  return { rate, area, total }
}

function withUnit(value: string, unit: string) {
  const v = normalizeNumericString(value)
  return v ? `${v} ${unit}` : ''
}

function normalizeLines(value: string) {
  return String(value || '')
    .split(/\r?\n/)
    .map((x) => normalizeSpaces(x))
    .filter(Boolean)
}

function normalizeList(value: string) {
  const raw = String(value || '')
  // allow comma/semicolon/newline separated
  return raw
    .split(/[,;\r\n]+/)
    .map((x) => normalizeSpaces(x))
    .filter(Boolean)
}

function formatObjectSummary(f: EntityFields) {
  const lines: string[] = []

  const addr = normalizeSpaces(f.object_address)
  if (addr) lines.push(`Адрес: ${addr}`)

  const typeLabel = formatObjectTypeLabel(f.object_type)
  if (typeLabel) lines.push(`Тип объекта: ${typeLabel}`)

  const rooms = normalizeNumericString(f.object_rooms_count)
  if (rooms) lines.push(`Количество комнат: ${rooms}`)

  const area = withUnit(f.object_area_sqm, 'м²')
  if (area) lines.push(`Площадь: ${area}`)

  const ceil = withUnit(f.object_ceiling_height_m, 'м')
  if (ceil) lines.push(`Высота потолков: ${ceil}`)

  const floor = normalizeNumericString(f.object_floor)
  const floorsTotal = normalizeNumericString(f.object_floors_total)
  if (floor || floorsTotal) {
    const frac = [floor || '—', floorsTotal || '—'].join('/')
    lines.push(`Этаж: ${frac}`)
  }

  const baths = normalizeNumericString(f.object_bathrooms_count)
  if (baths) lines.push(`Санузлов: ${baths}`)

  if (f.object_has_balcony === 'yes') lines.push('Балкон/лоджия: есть')
  if (f.object_has_balcony === 'no') lines.push('Балкон/лоджия: нет')

  return lines.join('\n')
}

function formatProjectBrief(f: EntityFields) {
  const lines: string[] = []
  const scope = formatProjectScopeLabel(f.project_scope)
  if (scope) lines.push(`Объём работ: ${scope}`)

  const style = normalizeSpaces(f.project_style)
  if (style) lines.push(`Стиль: ${style}`)

  const reno = formatRenovationTypeLabel(f.project_renovation_type)
  if (reno) lines.push(`Тип ремонта/исходное состояние: ${reno}`)

  const budget = normalizeSpaces(f.project_budget)
  if (budget) lines.push(`Бюджет: ${budget}`)

  const totalRaw = normalizeSpaces(f.project_price_total)
  const computed = computedProjectPrice(f)
  const rate = parseRatePerSqm(f)

  if (totalRaw) {
    // If user provided total explicitly, prefer it.
    if (rate != null && parseNumber(f.object_area_sqm) != null) {
      const area = withUnit(f.object_area_sqm, 'м²')
      const rateLabel = `${new Intl.NumberFormat('ru-RU').format(Math.round(rate))} ₽/м²`
      lines.push(`Стоимость работ: ${totalRaw} (${rateLabel} × ${area})`)
    } else {
      lines.push(`Стоимость работ: ${totalRaw}`)
    }
  } else if (computed) {
    const area = withUnit(String(computed.area), 'м²')
    const rateLabel = `${new Intl.NumberFormat('ru-RU').format(Math.round(computed.rate))} ₽/м²`
    lines.push(`Стоимость работ: ${formatRub(computed.total)} (${rateLabel} × ${area})`)
  } else {
    const legacy = normalizeSpaces(f.project_price)
    if (legacy) lines.push(`Стоимость работ: ${legacy}`)
  }

  const payment = normalizeSpaces(f.project_payment_terms)
  if (payment) lines.push(`Порядок оплаты: ${payment}`)

  const methods = formatPaymentMethodsInline(f)
  if (methods) lines.push(`Методы оплаты: ${methods}`)

  const deadline = normalizeSpaces(f.project_deadline)
  if (deadline) lines.push(`Сроки: ${deadline}`)

  const revisions = normalizeSpaces(f.project_revisions_included)
  if (revisions) lines.push(`Количество правок: ${revisions}`)

  const extraRevisions = normalizeSpaces(f.project_revision_extra_terms)
  if (extraRevisions) lines.push(`Доп. правки: ${extraRevisions}`)

  if (f.project_author_supervision === 'yes') lines.push('Авторский надзор: да')
  if (f.project_author_supervision === 'no') lines.push('Авторский надзор: нет')

  const visits = normalizeSpaces(f.project_site_visits_count)
  if (visits) lines.push(`Выезды/встречи: ${visits}`)

  const paidByLabel = formatSiteVisitsPaidByLabel(f.project_site_visits_paid_by)
  const paidByDetails = normalizeSpaces(f.project_site_visits_paid_by_details)
  if (paidByLabel || paidByDetails) {
    const rhs = [paidByLabel, paidByDetails].filter(Boolean).join(' — ')
    lines.push(`Кто оплачивает выезды: ${rhs}`)
  }

  const expenses = normalizeSpaces(f.project_site_visits_expenses)
  if (expenses) lines.push(`Расходы на выезды: ${expenses}`)

  const buysLabel = formatResponsibilityLabel(f.project_procurement_buys_paid_by)
  const buysDetails = normalizeSpaces(f.project_procurement_buys_details)
  if (buysLabel || buysDetails) {
    const rhs = [buysLabel, buysDetails].filter(Boolean).join(' — ')
    lines.push(`Закупки/оплата позиций: ${rhs}`)
  }

  const accLabel = formatResponsibilityLabel(f.project_procurement_delivery_acceptance_by)
  const accDetails = normalizeSpaces(f.project_procurement_delivery_acceptance_details)
  if (accLabel || accDetails) {
    const rhs = [accLabel, accDetails].filter(Boolean).join(' — ')
    lines.push(`Приём доставок: ${rhs}`)
  }

  const liftLabel = formatResponsibilityLabel(f.project_procurement_lifting_assembly_paid_by)
  const liftDetails = normalizeSpaces(f.project_procurement_lifting_assembly_details)
  if (liftLabel || liftDetails) {
    const rhs = [liftLabel, liftDetails].filter(Boolean).join(' — ')
    lines.push(`Подъём/сборка/монтаж: ${rhs}`)
  }

  const storageLabel = formatResponsibilityLabel(f.project_procurement_storage_paid_by)
  const storageDetails = normalizeSpaces(f.project_procurement_storage_details)
  if (storageLabel || storageDetails) {
    const rhs = [storageLabel, storageDetails].filter(Boolean).join(' — ')
    lines.push(`Хранение/складирование: ${rhs}`)
  }

  const handover = normalizeSpaces(f.project_handover_format)
  if (handover) lines.push(`Формат передачи: ${handover}`)

  const comm = normalizeSpaces(f.project_communication_details)
  if (comm) lines.push(`Коммуникация: ${comm}`)

  const commRules = normalizeSpaces(f.project_communication_rules)
  if (commRules) lines.push(`Правила связи: ${commRules}`)

  const sla = normalizeSpaces(f.project_approval_sla)
  if (sla) lines.push(`Согласование/ответы: ${sla}`)

  const shift = normalizeSpaces(f.project_deadline_shift_terms)
  if (shift) lines.push(`Сдвиг сроков при задержках: ${shift}`)

  const penalties = normalizeSpaces(f.project_penalties_terms)
  if (penalties) lines.push(`Штрафы/ответственность: ${penalties}`)

  const notes = normalizeSpaces(f.project_notes)
  if (notes) lines.push(`Примечания: ${notes}`)

  return lines.join('\n')
}

function formatDeliverablesLines(f: EntityFields) {
  const items: string[] = []

  if (f.deliverable_measurements) items.push('Обмерный план')
  if (f.deliverable_plan_solution) items.push('Планировочное решение')
  if (f.deliverable_demolition_plan) items.push('План демонтажа')
  if (f.deliverable_construction_plan) items.push('План монтажа/перегородок')
  if (f.deliverable_electric_plan) items.push('План электрики/розеток/выключателей')
  if (f.deliverable_plumbing_plan) items.push('План сантехники')
  if (f.deliverable_lighting_plan) items.push('План освещения')
  if (f.deliverable_ceiling_plan) items.push('План потолков')
  if (f.deliverable_floor_plan) items.push('План полов')
  if (f.deliverable_furniture_plan) items.push('План мебели/расстановки')
  if (f.deliverable_finishes_schedule) items.push('Ведомость отделки')
  if (f.deliverable_specification) items.push('Спецификация материалов/оборудования')
  if (f.deliverable_3d_visuals) items.push('3D‑визуализации')

  return items
}

function formatDeliverablesText(f: EntityFields) {
  const items = formatDeliverablesLines(f)
  if (items.length === 0) return ''
  return items.map((x) => `- ${x}`).join('\n')
}

function formatCommunicationChannelLabel(c: EntityFields['project_communication_channel']) {
  switch (c) {
    case 'telegram':
      return 'Telegram'
    case 'whatsapp':
      return 'WhatsApp'
    case 'email':
      return 'Email'
    case 'phone':
      return 'Телефон'
    case 'other':
      return 'Другое'
    default:
      return ''
  }
}

function formatSiteVisitsPaidByLabel(v: EntityFields['project_site_visits_paid_by']) {
  switch (v) {
    case 'customer':
      return 'Заказчик'
    case 'executor':
      return 'Исполнитель'
    case 'split':
      return 'Поровну/по договорённости'
    case 'other':
      return 'Другое'
    default:
      return ''
  }
}

function formatResponsibilityLabel(v: 'customer' | 'executor' | 'split' | 'other') {
  switch (v) {
    case 'customer':
      return 'Заказчик'
    case 'executor':
      return 'Исполнитель'
    case 'split':
      return 'Поровну/по договорённости'
    case 'other':
      return 'Другое'
    default:
      return ''
  }
}

function formatPaymentMethodsInline(f: EntityFields) {
  const items: string[] = []
  if (f.payment_method_cash) items.push('Наличные')
  if (f.payment_method_bank_transfer) items.push('Безналичный перевод')
  if (f.payment_method_card) items.push('Карта')
  if (f.payment_method_sbp) items.push('СБП')
  const other = normalizeSpaces(f.payment_method_other)
  if (other) items.push(other)
  return items.join(', ')
}

function formatCustomerStatusLabel(status: EntityFields['customer_status']) {
  switch (status) {
    case 'person':
      return 'Физлицо'
    case 'ip':
      return 'ИП'
    case 'self_employed':
      return 'Самозанятый'
    case 'company':
      return 'Юрлицо'
    default:
      return ''
  }
}

function formatInn(inn: string) {
  const digits = String(inn || '').replace(/\D+/g, '')
  if (!digits) return ''
  return digits
}

function formatRequisitesCustomer(f: EntityFields) {
  const lines: string[] = []
  const statusLabel = formatCustomerStatusLabel(f.customer_status)
  if (statusLabel) lines.push(`Статус: ${statusLabel}`)
  const fio = normalizeSpaces(f.customer_fio)
  if (fio) lines.push(`Заказчик: ${fio}`)
  const inn = formatInn(f.customer_inn)
  if (inn) lines.push(`ИНН: ${inn}`)
  const addr = normalizeSpaces(f.customer_address)
  if (addr) lines.push(`Адрес: ${addr}`)
  const phone = formatPhone(f.customer_phone)
  if (phone) lines.push(`Тел.: ${phone}`)
  const email = formatEmail(f.customer_email)
  if (email) lines.push(`Email: ${email}`)

  const tg = formatTelegram(f.customer_telegram)
  if (tg) lines.push(`Telegram: ${tg}`)
  const wa = formatWhatsapp(f.customer_whatsapp)
  if (wa) lines.push(`WhatsApp: ${wa}`)
  return lines.join('\n')
}

function formatRequisitesExecutor(f: EntityFields) {
  const lines: string[] = []
  const name = normalizeSpaces(f.executor_name)
  if (name) lines.push(`Исполнитель: ${name}`)
  const addr = normalizeSpaces(f.executor_address)
  if (addr) lines.push(`Адрес: ${addr}`)
  const inn = formatInn(f.executor_inn)
  if (inn) lines.push(`ИНН: ${inn}`)

  const phone = formatPhone(f.executor_phone)
  if (phone) lines.push(`Тел.: ${phone}`)
  const email = formatEmail(f.executor_email)
  if (email) lines.push(`Email: ${email}`)
  const tg = formatTelegram(f.executor_telegram)
  if (tg) lines.push(`Telegram: ${tg}`)
  return lines.join('\n')
}

function valueForPlaceholder(key: string, f: EntityFields) {
  // Normalize key variants: customer_fio -> customer.fio
  const k = key.replace(/_/g, '.').toLowerCase()

  switch (k) {
    case 'customer.fio':
      return normalizeSpaces(f.customer_fio)
    case 'customer.fio.short':
      return formatFioShort(f.customer_fio)
    case 'customer.status':
      return formatCustomerStatusLabel(f.customer_status)
    case 'customer.inn':
      return formatInn(f.customer_inn)
    case 'customer.address':
      return normalizeSpaces(f.customer_address)
    case 'customer.phone':
      return formatPhone(f.customer_phone)
    case 'customer.email':
      return formatEmail(f.customer_email)
    case 'customer.telegram':
      return formatTelegram(f.customer_telegram)
    case 'customer.whatsapp':
      return formatWhatsapp(f.customer_whatsapp)
    case 'customer.contacts': {
      const lines: string[] = []
      const phone = formatPhone(f.customer_phone)
      if (phone) lines.push(phone)
      const email = formatEmail(f.customer_email)
      if (email) lines.push(email)
      const tg = formatTelegram(f.customer_telegram)
      if (tg) lines.push(tg)
      const wa = formatWhatsapp(f.customer_whatsapp)
      if (wa) lines.push(wa)
      return lines.join('\n')
    }
    case 'customer.requisites':
      return formatRequisitesCustomer(f)

    case 'executor.name':
      return normalizeSpaces(f.executor_name)
    case 'executor.address':
      return normalizeSpaces(f.executor_address)
    case 'executor.inn':
      return formatInn(f.executor_inn)
    case 'executor.phone':
      return formatPhone(f.executor_phone)
    case 'executor.email':
      return formatEmail(f.executor_email)
    case 'executor.telegram':
      return formatTelegram(f.executor_telegram)
    case 'executor.contacts': {
      const lines: string[] = []
      const phone = formatPhone(f.executor_phone)
      if (phone) lines.push(phone)
      const email = formatEmail(f.executor_email)
      if (email) lines.push(email)
      const tg = formatTelegram(f.executor_telegram)
      if (tg) lines.push(tg)
      return lines.join('\n')
    }
    case 'executor.requisites':
      return formatRequisitesExecutor(f)

    case 'object.address':
      return normalizeSpaces(f.object_address)
    case 'object.address.line': {
      const addr = normalizeSpaces(f.object_address)
      return addr ? `Адрес объекта: ${addr}` : ''
    }
    case 'object.type':
      return formatObjectTypeLabel(f.object_type)
    case 'object.rooms':
    case 'object.rooms.count':
      return normalizeNumericString(f.object_rooms_count)
    case 'object.area':
    case 'object.area.sqm':
      return normalizeNumericString(f.object_area_sqm)
    case 'object.area.line': {
      const v = withUnit(f.object_area_sqm, 'м²')
      return v ? `Площадь: ${v}` : ''
    }
    case 'object.ceiling.height.m':
      return normalizeNumericString(f.object_ceiling_height_m)
    case 'object.ceiling.height.line': {
      const v = withUnit(f.object_ceiling_height_m, 'м')
      return v ? `Высота потолков: ${v}` : ''
    }
    case 'object.floor':
      return normalizeNumericString(f.object_floor)
    case 'object.floors.total':
      return normalizeNumericString(f.object_floors_total)
    case 'object.floor.fraction': {
      const floor = normalizeNumericString(f.object_floor)
      const total = normalizeNumericString(f.object_floors_total)
      if (!floor && !total) return ''
      return [floor || '—', total || '—'].join('/')
    }
    case 'object.bathrooms.count':
      return normalizeNumericString(f.object_bathrooms_count)
    case 'object.balcony':
      return f.object_has_balcony === 'yes' ? 'есть' : f.object_has_balcony === 'no' ? 'нет' : ''
    case 'object.summary':
      return formatObjectSummary(f)
    case 'object.rooms.list': {
      const items = normalizeList(f.object_rooms_list)
      return items.join('\n')
    }
    case 'object.residents.count':
      return normalizeNumericString(f.object_residents_count)
    case 'object.pets':
      return f.object_has_pets === 'yes' ? 'есть' : f.object_has_pets === 'no' ? 'нет' : ''
    case 'object.pets.notes':
      return normalizeSpaces(f.object_pets_notes)

    case 'project.scope':
      return formatProjectScopeLabel(f.project_scope)
    case 'project.style':
      return normalizeSpaces(f.project_style)
    case 'project.renovation.type':
      return formatRenovationTypeLabel(f.project_renovation_type)
    case 'project.budget':
      return normalizeSpaces(f.project_budget)
    case 'project.deadline':
      return normalizeSpaces(f.project_deadline)
    case 'project.notes':
      return normalizeSpaces(f.project_notes)
    case 'project.brief':
      return formatProjectBrief(f)
    case 'project.price':
      {
        const total = normalizeSpaces(f.project_price_total)
        if (total) return total
        const computed = computedProjectPrice(f)
        if (computed) return formatRub(computed.total)
        return normalizeSpaces(f.project_price)
      }
    case 'project.price.per_sqm': {
      const direct = normalizeSpaces(f.project_price_per_sqm)
      if (direct) {
        const n = parseNumber(direct)
        if (n != null) return `${new Intl.NumberFormat('ru-RU').format(Math.round(n))} ₽/м²`
        return direct
      }
      const rate = parsePricePerSqm(f.project_price)
      if (rate == null) return ''
      return `${new Intl.NumberFormat('ru-RU').format(Math.round(rate))} ₽/м²`
    }
    case 'project.payment.terms':
      return normalizeSpaces(f.project_payment_terms)
    case 'project.payment.methods':
      return formatPaymentMethodsInline(f)
    case 'project.revisions.included':
      return normalizeSpaces(f.project_revisions_included)
    case 'project.revisions.extra':
      return normalizeSpaces(f.project_revision_extra_terms)
    case 'project.author.supervision':
      return f.project_author_supervision === 'yes' ? 'да' : f.project_author_supervision === 'no' ? 'нет' : ''
    case 'project.site.visits.count':
      return normalizeSpaces(f.project_site_visits_count)
    case 'project.site.visits.paid_by': {
      const label = formatSiteVisitsPaidByLabel(f.project_site_visits_paid_by)
      const details = normalizeSpaces(f.project_site_visits_paid_by_details)
      return [label, details].filter(Boolean).join(' — ')
    }
    case 'project.site.visits.expenses':
      return normalizeSpaces(f.project_site_visits_expenses)

    case 'project.procurement.buys.paid_by': {
      const label = formatResponsibilityLabel(f.project_procurement_buys_paid_by)
      const details = normalizeSpaces(f.project_procurement_buys_details)
      return [label, details].filter(Boolean).join(' — ')
    }
    case 'project.procurement.delivery.acceptance_by': {
      const label = formatResponsibilityLabel(f.project_procurement_delivery_acceptance_by)
      const details = normalizeSpaces(f.project_procurement_delivery_acceptance_details)
      return [label, details].filter(Boolean).join(' — ')
    }
    case 'project.procurement.lifting.assembly.paid_by': {
      const label = formatResponsibilityLabel(f.project_procurement_lifting_assembly_paid_by)
      const details = normalizeSpaces(f.project_procurement_lifting_assembly_details)
      return [label, details].filter(Boolean).join(' — ')
    }
    case 'project.procurement.storage.paid_by': {
      const label = formatResponsibilityLabel(f.project_procurement_storage_paid_by)
      const details = normalizeSpaces(f.project_procurement_storage_details)
      return [label, details].filter(Boolean).join(' — ')
    }

    case 'project.approval.sla':
      return normalizeSpaces(f.project_approval_sla)
    case 'project.deadline.shift.terms':
      return normalizeSpaces(f.project_deadline_shift_terms)
    case 'project.penalties.terms':
      return normalizeSpaces(f.project_penalties_terms)
    case 'project.handover.format':
      return normalizeSpaces(f.project_handover_format)
    case 'project.communication.channel':
      return formatCommunicationChannelLabel(f.project_communication_channel)
    case 'project.communication.details':
      return normalizeSpaces(f.project_communication_details)
    case 'project.communication.rules':
      return normalizeSpaces(f.project_communication_rules)
    case 'project.communication': {
      const parts: string[] = []
      const ch = formatCommunicationChannelLabel(f.project_communication_channel)
      if (ch) parts.push(ch)
      const d = normalizeSpaces(f.project_communication_details)
      if (d) parts.push(d)
      return parts.join(': ')
    }
    case 'project.deliverables':
    case 'project.deliverables.list':
      return formatDeliverablesText(f)
    case 'project.deliverables.inline': {
      const items = formatDeliverablesLines(f)
      return items.join(', ')
    }
    default:
      return ''
  }
}

function applyTemplate(text: string, fields: EntityFields) {
  return text.replace(/\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}/g, (full, key) => {
    const v = valueForPlaceholder(String(key), fields)
    if (!v) return full
    return v
  })
}

function filterKey(f: TypeFilter) {
  if (f.mode === 'all') return 'all'
  if (f.mode === 'untyped') return 'untyped'
  return `type:${f.typeId}`
}

export default function DocumentsScreen(props: DocumentsScreenProps) {
  const { setContent } = usePropertiesSlot()
  const [docs, setDocs] = React.useState<DocumentIndexItem[]>([])
  const [types, setTypes] = React.useState<DocumentType[]>([])
  const [typesLoading, setTypesLoading] = React.useState(false)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  const [typeFilter, setTypeFilter] = React.useState<TypeFilter>({ mode: 'all' })
  const [expanded, setExpanded] = React.useState<Set<string>>(() => new Set(['untyped']))

  const [selected, setSelected] = React.useState<Selection | null>(null)
  const [selectedVersionId, setSelectedVersionId] = React.useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = React.useState(false)
  const [previewError, setPreviewError] = React.useState<string | null>(null)
  const [previewText, setPreviewText] = React.useState<string | null>(null)

  const [applyingEntities, setApplyingEntities] = React.useState(false)
  const [generatingFromAI, setGeneratingFromAI] = React.useState(false)
  const [extractingEntities, setExtractingEntities] = React.useState(false)
  const [savingToGoogleDocs, setSavingToGoogleDocs] = React.useState(false)
  const [lastGoogleDocLink, setLastGoogleDocLink] = React.useState<string | null>(null)

  const [entityFields, setEntityFields] = React.useState<EntityFields>({
    customer_status: 'person',
    customer_fio: '',
    customer_address: '',
    customer_phone: '',
    customer_email: '',
    customer_inn: '',
    customer_telegram: '',
    customer_whatsapp: '',
    executor_name: '',
    executor_address: '',
    executor_inn: '',
    executor_phone: '',
    executor_email: '',
    executor_telegram: '',
    object_address: '',
    object_type: 'apartment',
    object_rooms_count: '',
    object_area_sqm: '',
    object_ceiling_height_m: '',
    object_floor: '',
    object_floors_total: '',
    object_bathrooms_count: '',
    object_has_balcony: 'no',
    object_rooms_list: '',
    object_residents_count: '',
    object_has_pets: 'no',
    object_pets_notes: '',
    project_scope: 'full',
    project_style: '',
    project_renovation_type: 'new_build',
    project_budget: '',
    project_deadline: '',
    project_notes: '',
    project_price: '',
    project_price_per_sqm: '',
    project_price_total: '',
    project_payment_terms: '',
    payment_method_cash: false,
    payment_method_bank_transfer: true,
    payment_method_card: false,
    payment_method_sbp: true,
    payment_method_other: '',
    project_revisions_included: '',
    project_revision_extra_terms: '',
    project_author_supervision: 'no',
    project_site_visits_count: '',
    project_site_visits_paid_by: 'customer',
    project_site_visits_paid_by_details: '',
    project_site_visits_expenses: '',

    project_procurement_buys_paid_by: 'customer',
    project_procurement_buys_details: '',
    project_procurement_delivery_acceptance_by: 'customer',
    project_procurement_delivery_acceptance_details: '',
    project_procurement_lifting_assembly_paid_by: 'customer',
    project_procurement_lifting_assembly_details: '',
    project_procurement_storage_paid_by: 'customer',
    project_procurement_storage_details: '',

    project_approval_sla: '',
    project_deadline_shift_terms: '',
    project_penalties_terms: '',
    project_handover_format: '',
    project_communication_channel: 'telegram',
    project_communication_details: '',
    project_communication_rules: '',
    deliverable_measurements: true,
    deliverable_plan_solution: true,
    deliverable_demolition_plan: false,
    deliverable_construction_plan: true,
    deliverable_electric_plan: true,
    deliverable_plumbing_plan: true,
    deliverable_lighting_plan: true,
    deliverable_ceiling_plan: false,
    deliverable_floor_plan: false,
    deliverable_furniture_plan: true,
    deliverable_finishes_schedule: true,
    deliverable_specification: true,
    deliverable_3d_visuals: true,
  })

  // Auto-calc total price from rate×area, but don't overwrite a user-edited total.
  const lastAutoTotalRef = React.useRef<string>('')
  React.useEffect(() => {
    const computed = computedProjectPrice(entityFields)
    if (!computed) return
    const nextAuto = formatRub(computed.total)

    setEntityFields((prev) => {
      // Only auto-fill when the field is empty or still equals the last auto value.
      const current = normalizeSpaces(prev.project_price_total)
      const lastAuto = lastAutoTotalRef.current
      if (current && current !== lastAuto) return prev

      if (current === nextAuto) {
        lastAutoTotalRef.current = nextAuto
        return prev
      }
      lastAutoTotalRef.current = nextAuto
      return { ...prev, project_price_total: nextAuto }
    })
  }, [entityFields.object_area_sqm, entityFields.project_price_per_sqm, entityFields.project_price])

  const [createTitle, setCreateTitle] = React.useState('')
  const [createText, setCreateText] = React.useState('')
  const [createFile, setCreateFile] = React.useState<File | null>(null)
  const [creating, setCreating] = React.useState(false)

  const [addText, setAddText] = React.useState('')
  const [addFile, setAddFile] = React.useState<File | null>(null)
  const [adding, setAdding] = React.useState(false)

  const [chatText, setChatText] = React.useState('')
  const [chatLog, setChatLog] = React.useState<Array<{ id: string; role: 'user' | 'bot'; text: string }>>([])
  const [chatSending, setChatSending] = React.useState(false)

  function lastUserChatText() {
    for (let i = chatLog.length - 1; i >= 0; i--) {
      const m = chatLog[i]
      if (m.role === 'user') return normalizeSpaces(m.text)
    }
    return ''
  }

  function toAIChatMessages(nextUserText?: string): AIChatMessage[] {
    const base: AIChatMessage[] = chatLog
      .slice(-20)
      .map<AIChatMessage>((m) => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        text: String(m.text || ''),
      }))
      .filter((m) => normalizeSpaces(m.text))

    if (nextUserText && normalizeSpaces(nextUserText)) {
      return [...base, { role: 'user', text: nextUserText } satisfies AIChatMessage]
    }
    return base
  }

  const [orLoading, setOrLoading] = React.useState(false)
  const [orError, setOrError] = React.useState<string | null>(null)
  const [orApiKeyInput, setOrApiKeyInput] = React.useState('')
  const [orKeys, setOrKeys] = React.useState<OpenRouterKey[]>([])
  const [orModels, setOrModels] = React.useState<OpenRouterModel[]>([])
  const [orActiveKeyId, setOrActiveKeyId] = React.useState<string>('')
  const [orModelId, setOrModelId] = React.useState<string>('')

  const refreshOpenRouter = React.useCallback(async () => {
    if (!props.isAuthed) {
      setOrError(null)
      setOrKeys([])
      setOrModels([])
      setOrActiveKeyId('')
      setOrModelId('')
      return
    }
    setOrLoading(true)
    setOrError(null)
    try {
      const [cfg, keys, models] = await Promise.all([
        getOpenRouterConfig(),
        listOpenRouterKeys(),
        listOpenRouterModels(),
      ])
      setOrKeys(keys)
      setOrModels(models)
      setOrActiveKeyId(cfg.active_key_id || '')
      setOrModelId(cfg.model || '')
    } catch (e: any) {
      const msg = String(e?.message || '')
      if (msg.includes('401') || msg.toLowerCase().includes('missing bearer token')) {
        setOrError('Нужна авторизация: войдите в аккаунт сверху.')
      } else {
        setOrError(e?.message || 'Не удалось загрузить настройки OpenRouter')
      }
    } finally {
      setOrLoading(false)
    }
  }, [props.isAuthed])

  React.useEffect(() => {
    refreshOpenRouter().catch(() => {})
  }, [refreshOpenRouter])

  async function sendChat() {
    const text = chatText.trim()
    if (!text || chatSending) return

    if (!props.isAuthed) {
      setError('Нужна авторизация: войдите в аккаунт сверху.')
      return
    }

    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    setChatLog((prev) => [...prev, { id, role: 'user', text }])
    setChatText('')

    setChatSending(true)
    setError(null)
    try {
      const resp = await aiChat({
        version_id: selectedVersionId || null,
        messages: toAIChatMessages(text),
      })
      const botId = `${Date.now()}-${Math.random().toString(16).slice(2)}`
      setChatLog((prev) => [...prev, { id: botId, role: 'bot', text: resp.text }])
    } catch (e: any) {
      setError(e?.message || 'Чат не работает')
    } finally {
      setChatSending(false)
    }
  }

  function sendChatPreset(text: string) {
    const t = normalizeSpaces(text)
    if (!t) return
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    setChatLog((prev) => [...prev, { id, role: 'user', text: t }])
  }

  function applyExtractedEntities(raw: any) {
    if (!raw || typeof raw !== 'object') return

    const enums = {
      customer_status: ['person', 'ip', 'self_employed', 'company'],
      object_type: ['apartment', 'house', 'commercial', 'other'],
      object_has_balcony: ['no', 'yes'],
      object_has_pets: ['no', 'yes'],
      project_scope: ['full', 'rooms_only', 'consultation', 'other'],
      project_renovation_type: ['new_build', 'secondary', 'cosmetic', 'capital', 'other'],
      project_author_supervision: ['no', 'yes'],
      project_communication_channel: ['telegram', 'whatsapp', 'email', 'phone', 'other'],
      project_site_visits_paid_by: ['customer', 'executor', 'split', 'other'],
      project_procurement_buys_paid_by: ['customer', 'executor', 'split', 'other'],
      project_procurement_delivery_acceptance_by: ['customer', 'executor', 'split', 'other'],
      project_procurement_lifting_assembly_paid_by: ['customer', 'executor', 'split', 'other'],
      project_procurement_storage_paid_by: ['customer', 'executor', 'split', 'other'],
    } as const

    setEntityFields((prev) => {
      const next: any = { ...prev }
      for (const [k, v] of Object.entries(raw)) {
        if (!(k in prev)) continue

        const prevVal: any = (prev as any)[k]
        if (typeof prevVal === 'boolean') {
          if (typeof v === 'boolean') next[k] = v
          else if (typeof v === 'string') {
            const s = v.trim().toLowerCase()
            if (s === 'true') next[k] = true
            if (s === 'false') next[k] = false
          }
          continue
        }

        if ((enums as any)[k]) {
          const allowed: string[] = (enums as any)[k]
          const s = String(v ?? '').trim()
          if (allowed.includes(s)) next[k] = s
          continue
        }

        // string fields
        if (typeof prevVal === 'string') {
          if (v === null || v === undefined) continue
          next[k] = String(v)
        }
      }
      return next
    })
  }

  async function onExtractEntitiesFromAI() {
    if (!selected || !selectedVersionId) {
      setError('Выберите документ и версию для извлечения сущностей.')
      return
    }

    const version = selected.versions.find((v) => v.id === selectedVersionId)
    if (!version) {
      setError('Версия не найдена.')
      return
    }

    if (!version.content_type.startsWith('text/')) {
      setError('Извлечение сущностей доступно только для текстовых версий.')
      return
    }

    const raw = normalizeSpaces(chatText)
    const instructions = raw || lastUserChatText()

    setExtractingEntities(true)
    setError(null)
    try {
      if (raw) {
        const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
        setChatLog((prev) => [...prev, { id, role: 'user', text: raw }])
        setChatText('')
      }

      const resp = await aiExtractEntities({ version_id: version.id, instructions: instructions || null })
      const botId = `${Date.now()}-${Math.random().toString(16).slice(2)}`
      setChatLog((prev) => [...prev, { id: botId, role: 'bot', text: resp.raw_text }])
      applyExtractedEntities(resp.data)
    } catch (e: any) {
      setError(e?.message || 'Failed to extract entities')
    } finally {
      setExtractingEntities(false)
    }
  }

  async function onGenerateDocumentFromAI() {
    const base = previewText || ''

    // Keep UI navigable: after generation we will switch filter to where the new doc will appear.
    const createdTypeId = selected?.doc?.type_id || null

    // Minimal UX: allow without base version, but warn if nothing to guide the model.
    const hasBase = Boolean(base.trim())
    const rawInstruction = normalizeSpaces(chatText)
    const instruction = rawInstruction || lastUserChatText()
    if (!hasBase && !instruction) {
      setError('Введите запрос в чат или выберите версию документа как основу.')
      return
    }

    const who = formatFioShort(entityFields.customer_fio)
    const suffix = who ? ` — ${who}` : ''
    const baseTitle = selected?.doc?.title || 'Документ'
    const title = `${baseTitle}${suffix} (ИИ)`

    setGeneratingFromAI(true)
    setError(null)
    try {
      // Log user intent into chat
      if (rawInstruction) {
        const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
        setChatLog((prev) => [...prev, { id, role: 'user', text: rawInstruction }])
        setChatText('')
      }

      let templateText: string | null = null
      try {
        const ai = await aiGenerateTemplate({
          base_text: hasBase ? base : null,
          instructions: instruction || null,
          entities: entityFields as any,
        })

        templateText = ai.text

        const botId = `${Date.now()}-${Math.random().toString(16).slice(2)}`
        setChatLog((prev) => [...prev, { id: botId, role: 'bot', text: ai.text }])
      } catch (e: any) {
        const msg = String(e?.message || '')
        const aiDisabled = msg.includes('MODEL_PROVIDER=none') || msg.includes('AI is disabled')
        if (!aiDisabled) throw e

        if (!hasBase) {
          setError('ИИ отключен. Выберите версию документа как основу (или включите AI в backend/.env).')
          return
        }

        const rendered = base.includes('{{') ? applyTemplate(base, entityFields) : base
        templateText = rendered

        const botId = `${Date.now()}-${Math.random().toString(16).slice(2)}`
        setChatLog((prev) => [
          ...prev,
          { id: botId, role: 'bot', text: 'ИИ отключен — создал документ из текущей версии с подстановкой сущностей.' },
        ])
      }

      const finalText = templateText ? applyTemplate(templateText, entityFields) : ''

      const created = await createDocumentFromText(title, finalText, createdTypeId)
      const items = await listDocumentsIndex()
      setDocs(items)

      // If the current filter would hide the newly created document, switch to the matching bucket.
      // This prevents the "не генерирует" UX when a doc is created but not visible due to filtering.
      if (typeFilter.mode !== 'all') {
        setTypeFilter(createdTypeId ? { mode: 'type', typeId: createdTypeId } : { mode: 'untyped' })
      }

      const docItem: DocumentIndexItem =
        items.find((d) => d.id === created.document.id) ||
        ({
          id: created.document.id,
          title: created.document.title,
          created_at: created.document.created_at,
          type_id: selected?.doc?.type_id || null,
          latest_version_id: created.version.id,
          latest_version_created_at: created.version.created_at,
          latest_version_content_type: created.version.content_type,
        } satisfies DocumentIndexItem)

      const versions = await listDocumentVersions(docItem.id)
      setSelected({ doc: docItem, versions })
      setSelectedVersionId(created.version.id)
    } catch (e: any) {
      setError(e?.message || 'Failed to generate with AI')
    } finally {
      setGeneratingFromAI(false)
    }
  }

  const propertiesNode = React.useMemo(() => {
    return (
      <EntitiesPanel
        selected={selected}
        selectedVersionId={selectedVersionId}
        applyingEntities={applyingEntities}
        entityFields={entityFields}
        onChangeEntityFields={setEntityFields}
        createTitle={createTitle}
        createText={createText}
        creating={creating}
        onCreate={onCreate}
        onApplyEntitiesToDocument={onApplyEntitiesToDocument}
        onChangeFile={(f) => setCreateFile(f)}
        onChangeText={setCreateText}
        onChangeTitle={setCreateTitle}
        addText={addText}
        adding={adding}
        onAddVersion={onAddVersion}
        onChangeAddFile={(f) => setAddFile(f)}
        onChangeAddText={setAddText}
      />
    )
  }, [selected, selectedVersionId, applyingEntities, entityFields, createTitle, createText, creating, addText, adding])

  const renderedPreviewText = React.useMemo(() => {
    if (!previewText) return ''
    if (!previewText.includes('{{')) return previewText
    return applyTemplate(previewText, entityFields)
  }, [previewText, entityFields])

  async function reload() {
    setLoading(true)
    setError(null)
    try {
      const items = await listDocumentsIndex()
      setDocs(items)
    } catch (e: any) {
      setError(e?.message || 'Failed to load')
    } finally {
      setLoading(false)
    }
  }

  React.useEffect(() => {
    reload()
  }, [])

  React.useEffect(() => {
    ;(async () => {
      setTypesLoading(true)
      try {
        const items = await listDocumentTypes()
        setTypes(items)
      } catch (e: any) {
        setError(e?.message || 'Failed to load document types')
      } finally {
        setTypesLoading(false)
      }
    })()
  }, [])

  React.useEffect(() => {
    setContent(propertiesNode)
    return () => setContent(null)
  }, [propertiesNode, setContent])

  async function selectDoc(doc: DocumentIndexItem) {
    setError(null)
    try {
      const versions = await listDocumentVersions(doc.id)
      setSelected({ doc, versions })
      setSelectedVersionId(versions[0]?.id || null)
    } catch (e: any) {
      setError(e?.message || 'Failed to load versions')
    }
  }

  async function loadPreview(version: DocumentVersion) {
    setSelectedVersionId(version.id)
    setPreviewError(null)
    setPreviewText(null)

    if (!version.content_type?.startsWith('text/')) {
      setPreviewText(`(binary artifact; content_type=${version.content_type})`)
      return
    }

    setPreviewLoading(true)
    try {
      const text = await fetchVersionArtifactText(version.id)
      setPreviewText(text)
    } catch (e: any) {
      setPreviewError(e?.message || 'Failed to load preview')
    } finally {
      setPreviewLoading(false)
    }
  }

  React.useEffect(() => {
    if (!selected || !selectedVersionId) {
      setPreviewText(null)
      setPreviewError(null)
      return
    }
    const v = selected.versions.find((x) => x.id === selectedVersionId)
    if (!v) return

    let cancelled = false
    ;(async () => {
      setPreviewText(null)
      setPreviewLoading(true)
      setPreviewError(null)
      try {
        if (!v.content_type?.startsWith('text/')) {
          if (!cancelled) setPreviewText(`(binary artifact; content_type=${v.content_type})`)
          return
        }
        const text = await fetchVersionArtifactText(v.id)
        if (!cancelled) setPreviewText(text)
      } catch (e: any) {
        if (!cancelled) setPreviewError(e?.message || 'Failed to load preview')
      } finally {
        if (!cancelled) setPreviewLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [selected, selectedVersionId])

  async function onCreate() {
    if (!createTitle.trim()) {
      setError('Введите название документа')
      return
    }

    if (!createFile && !createText.trim()) {
      setError('Добавьте текст или выберите файл')
      return
    }

    setCreating(true)
    setError(null)
    try {
      const typeId = typeFilter.mode === 'type' ? typeFilter.typeId : null
      if (createFile) {
        await createDocumentFromFile(createTitle.trim(), createFile, typeId)
      } else {
        await createDocumentFromText(createTitle.trim(), createText, typeId)
      }
      setCreateTitle('')
      setCreateText('')
      setCreateFile(null)
      await reload()
    } catch (e: any) {
      setError(e?.message || 'Failed to create')
    } finally {
      setCreating(false)
    }
  }

  const selectedTypeTitle = React.useMemo(() => {
    if (typeFilter.mode === 'all') return 'Все документы'
    if (typeFilter.mode === 'untyped') return 'Без типа'
    return types.find((t) => t.id === typeFilter.typeId)?.title || 'Тип'
  }, [typeFilter, types])

  const visibleDocs = React.useMemo(() => {
    if (typeFilter.mode === 'all') return docs
    if (typeFilter.mode === 'untyped') return docs.filter((d) => !d.type_id)
    return docs.filter((d) => d.type_id === typeFilter.typeId)
  }, [docs, typeFilter])

  const docsByType = React.useMemo(() => {
    const byTypeId = new Map<string, DocumentIndexItem[]>()
    const untyped: DocumentIndexItem[] = []

    for (const d of docs) {
      if (!d.type_id) {
        untyped.push(d)
        continue
      }
      const bucket = byTypeId.get(d.type_id)
      if (bucket) bucket.push(d)
      else byTypeId.set(d.type_id, [d])
    }

    return { byTypeId, untyped }
  }, [docs])

  React.useEffect(() => {
    // Keep current filter expanded so the tree stays navigable.
    setExpanded((prev) => {
      const next = new Set(prev)
      next.add(filterKey(typeFilter))
      return next
    })
  }, [typeFilter])

  async function onAddVersion() {
    if (!selected) {
      setError('Сначала выберите документ')
      return
    }

    if (!addFile && !addText.trim()) {
      setError('Добавьте текст версии или выберите файл')
      return
    }

    setAdding(true)
    setError(null)
    try {
      if (addFile) {
        await addVersionFromFile(selected.doc.id, addFile)
      } else {
        await addVersionFromText(selected.doc.id, addText)
      }
      setAddText('')
      setAddFile(null)

      const versions = await listDocumentVersions(selected.doc.id)
      setSelected({ doc: selected.doc, versions })
      setSelectedVersionId(versions[0]?.id || null)
      await reload()
    } catch (e: any) {
      setError(e?.message || 'Failed to add version')
    } finally {
      setAdding(false)
    }
  }

  async function onApplyEntitiesToDocument() {
    if (!selected) {
      setError('Сначала выберите документ')
      return
    }
    if (!selectedVersionId) {
      setError('Сначала выберите версию')
      return
    }

    const v = selected.versions.find((x) => x.id === selectedVersionId)
    if (!v) {
      setError('Версия не найдена')
      return
    }
    if (!v.content_type?.startsWith('text/')) {
      setError('Подстановка работает только для текстовых версий')
      return
    }
    if (!previewText) {
      setError('Сначала откройте версию, чтобы загрузить текст')
      return
    }
    if (!previewText.includes('{{')) {
      setError('В тексте нет плейсхолдеров вида {{...}}')
      return
    }

    const rendered = applyTemplate(previewText, entityFields)
    if (rendered === previewText) {
      setError('Плейсхолдеры не заменились (проверьте ключи вида {{customer.requisites}})')
      return
    }

    setApplyingEntities(true)
    setError(null)
    try {
      const newVersion = await addVersionFromText(selected.doc.id, rendered)
      const versions = await listDocumentVersions(selected.doc.id)
      setSelected({ doc: selected.doc, versions })
      setSelectedVersionId(newVersion.id)
      await reload()
    } catch (e: any) {
      setError(e?.message || 'Failed to apply entities')
    } finally {
      setApplyingEntities(false)
    }
  }

  async function onSavePreviewToGoogleDocs() {
    if (!selected || !selectedVersionId) {
      setError('Выберите документ и версию для сохранения в Google Docs.')
      return
    }

    const v = selected.versions.find((x) => x.id === selectedVersionId)
    if (!v) {
      setError('Версия не найдена')
      return
    }
    if (!v.content_type?.startsWith('text/')) {
      setError('Сохранение в Google Docs доступно только для текстовых версий')
      return
    }
    if (!previewText) {
      setError('Сначала откройте версию, чтобы загрузить текст')
      return
    }

    setSavingToGoogleDocs(true)
    setError(null)
    try {
      const resp = await saveToGoogleDocs({
        version_id: v.id,
        title: selected.doc.title,
        text: renderedPreviewText,
      })
      const link = resp.web_view_link || null
      setLastGoogleDocLink(link)
      if (link) window.open(link, '_blank', 'noreferrer')
    } catch (e: any) {
      setError(e?.message || 'Failed to save to Google Docs')
    } finally {
      setSavingToGoogleDocs(false)
    }
  }

  return (
    <div className="stack">
      <div className="row row-space">
        <div>
          <h1 className="h1">Документы</h1>
          <p className="muted">Слева выберите тип или документ. Редактор — справа.</p>
        </div>
        <button className="btn" type="button" onClick={reload} disabled={loading}>
          Обновить
        </button>
      </div>

      {error ? <div className="alert">{error}</div> : null}

      <section className="card">
        <h2 className="h2">Просмотр версии</h2>
        {selected && selectedVersionId ? (
          <div className="row row-wrap">
            <button
              className="btn"
              type="button"
              title="Скачать исходный артефакт версии"
              onClick={async () => {
                try {
                  const blob = await downloadVersionArtifactBlob(selectedVersionId)
                  const objUrl = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = objUrl
                  a.download = `version-${selectedVersionId}.txt`
                  document.body.appendChild(a)
                  a.click()
                  a.remove()
                  setTimeout(() => URL.revokeObjectURL(objUrl), 1000)
                } catch (e: any) {
                  setError(e?.message || 'Не удалось скачать')
                }
              }}
            >
              Скачать
            </button>
            <button
              className="btn"
              type="button"
              onClick={onSavePreviewToGoogleDocs}
              disabled={savingToGoogleDocs}
              title="Сохраняет текущий предпросмотр (с подставленными сущностями) в Google Docs"
            >
              {savingToGoogleDocs ? 'Сохраняю в Google Docs…' : 'В Google Docs'}
            </button>
            {lastGoogleDocLink ? (
              <a className="btn" href={lastGoogleDocLink} target="_blank" rel="noreferrer">
                Открыть
              </a>
            ) : null}
          </div>
        ) : null}
        {!selected || !selectedVersionId ? (
          <div className="muted">Выберите документ и версию.</div>
        ) : previewLoading ? (
          <div className="muted">Загрузка…</div>
        ) : previewError ? (
          <div className="alert">{previewError}</div>
        ) : (
          <pre className="preview">{renderedPreviewText}</pre>
        )}
      </section>

      <section className="card">
        <h2 className="h2">Чат-бот</h2>
        <div className="chat-layout">
          <div className="chat-window" aria-label="Окно чата">
            {chatLog.length === 0 ? (
              <div className="muted">Пока нет сообщений.</div>
            ) : (
              <div className="stack-tight">
                {chatLog.map((m) => (
                  <div key={m.id} className={`chat-msg ${m.role === 'bot' ? 'bot' : 'user'}`}>
                    <div className="muted">{m.role === 'bot' ? 'Бот' : 'Вы'}</div>
                    <div>{m.text}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="chat-input-row">
            <input
              value={chatText}
              disabled={chatSending}
              onChange={(e) => setChatText(e.target.value)}
              placeholder={props.isAuthed ? 'Введите сообщение…' : 'Войдите в аккаунт, чтобы пользоваться чатом'}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendChat()
                }
              }}
            />
            <button className="btn" type="button" onClick={sendChat} disabled={chatSending || !props.isAuthed}>
              {chatSending ? 'Отправляю…' : 'Отправить'}
            </button>
          </div>

          <div className="chat-menu" aria-label="Меню чат-бота">
            <div className="stack-tight">
              <div className="muted">Меню</div>

              {!props.isAuthed ? <div className="alert">Войдите в аккаунт, чтобы настроить OpenRouter.</div> : null}

              {orError ? <div className="alert">{orError}</div> : null}

              <div className="row row-wrap" aria-label="OpenRouter настройки">
                <input
                  value={orApiKeyInput}
                  onChange={(e) => setOrApiKeyInput(e.target.value)}
                  placeholder="OpenRouter API key"
                  type="password"
                  style={{ maxWidth: 320 }}
                />
                <button
                  className="btn"
                  type="button"
                  disabled={!props.isAuthed || orLoading || !orApiKeyInput.trim()}
                  onClick={async () => {
                    const key = orApiKeyInput.trim()
                    if (!key) return
                    setOrLoading(true)
                    setOrError(null)
                    try {
                      await createOpenRouterKey({ api_key: key })
                      setOrApiKeyInput('')
                      await refreshOpenRouter()
                    } catch (e: any) {
                      setOrError(e?.message || 'Не удалось добавить ключ')
                    } finally {
                      setOrLoading(false)
                    }
                  }}
                >
                  {orLoading ? 'Добавляю…' : 'Добавить ключ'}
                </button>
                <button className="btn" type="button" disabled={!props.isAuthed || orLoading} onClick={refreshOpenRouter}>
                  Обновить модели
                </button>
              </div>

              <label className="field">
                <span className="field-label">Ключ</span>
                <select
                  value={orActiveKeyId}
                  disabled={!props.isAuthed || orLoading || orKeys.length === 0}
                  onChange={async (e) => {
                    const id = e.target.value
                    setOrActiveKeyId(id)
                    setOrLoading(true)
                    setOrError(null)
                    try {
                      await setOpenRouterActive({ active_key_id: id })
                      await refreshOpenRouter()
                    } catch (err: any) {
                      setOrError(err?.message || 'Не удалось выбрать ключ')
                    } finally {
                      setOrLoading(false)
                    }
                  }}
                >
                  {orKeys.length === 0 ? <option value="">(нет ключей)</option> : null}
                  {orKeys.map((k) => (
                    <option key={k.id} value={k.id}>
                      {k.label ? k.label : k.id.slice(0, 8)}{k.is_active ? ' (активный)' : ''}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span className="field-label">Модель</span>
                <select
                  value={orModelId}
                  disabled={!props.isAuthed || orLoading || !orActiveKeyId || orModels.length === 0}
                  onChange={async (e) => {
                    const id = e.target.value
                    setOrModelId(id)
                    setOrLoading(true)
                    setOrError(null)
                    try {
                      await setOpenRouterActive({ model: id })
                      await refreshOpenRouter()
                    } catch (err: any) {
                      setOrError(err?.message || 'Не удалось выбрать модель')
                    } finally {
                      setOrLoading(false)
                    }
                  }}
                >
                  {orModels.length === 0 ? <option value="">(модели не загружены)</option> : null}
                  {orModels.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.id}
                    </option>
                  ))}
                </select>
              </label>

              <button className="btn" type="button" disabled>
                Суммаризация (скоро)
              </button>
              <button
                className="btn"
                type="button"
                onClick={onExtractEntitiesFromAI}
                disabled={!props.isAuthed || !selected || !selectedVersionId || extractingEntities}
                title="ИИ извлекает сущности из выбранной версии и заполняет поля справа"
              >
                {extractingEntities ? 'Извлекаю…' : 'Извлечь сущности'}
              </button>
              <button
                className="btn"
                type="button"
                onClick={onGenerateDocumentFromAI}
                disabled={!props.isAuthed || generatingFromAI}
                title="ИИ генерирует шаблон с плейсхолдерами, затем создаёт новый документ"
              >
                {generatingFromAI ? 'Генерирую…' : 'Сгенерировать документ'}
              </button>
            </div>
          </div>
        </div>
      </section>

      <div className="split">
        <section className="card">
          <h2 className="h2">Типы → документы</h2>
          {typesLoading ? (
            <div className="muted">Загрузка…</div>
          ) : types.length === 0 ? (
            <div className="muted">Пока нет типов</div>
          ) : null}

          <div className="nav">
            <button
              type="button"
              className={`nav-item ${typeFilter.mode === 'all' ? 'active' : ''}`}
              onClick={() => setTypeFilter({ mode: 'all' })}
            >
              Все документы
            </button>

            <div className="nav-group">
              <button
                type="button"
                className={`nav-item ${typeFilter.mode === 'untyped' ? 'active' : ''}`}
                onClick={() => {
                  setTypeFilter({ mode: 'untyped' })
                  setExpanded((prev) => {
                    const next = new Set(prev)
                    const k = filterKey({ mode: 'untyped' })
                    if (next.has(k)) next.delete(k)
                    else next.add(k)
                    return next
                  })
                }}
              >
                {expanded.has('untyped') ? '▾' : '▸'} Без типа
              </button>
              {docsByType.untyped.length > 0 && expanded.has('untyped') ? (
                <div className="nav-sub">
                  {docsByType.untyped.map((d) => (
                    <button
                      key={d.id}
                      type="button"
                      className={`nav-item sub ${selected?.doc.id === d.id ? 'active' : ''}`}
                      onClick={() => {
                        setTypeFilter({ mode: 'untyped' })
                        selectDoc(d)
                      }}
                      title={d.id}
                    >
                      {d.title}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            {types.map((t) => {
              const items = docsByType.byTypeId.get(t.id) || []
              const k = filterKey({ mode: 'type', typeId: t.id })
              const isExpanded = expanded.has(k)
              return (
                <div key={t.id} className="nav-group">
                  <button
                    type="button"
                    className={`nav-item ${typeFilter.mode === 'type' && typeFilter.typeId === t.id ? 'active' : ''}`}
                    onClick={() => {
                      setTypeFilter({ mode: 'type', typeId: t.id })
                      setExpanded((prev) => {
                        const next = new Set(prev)
                        if (next.has(k)) next.delete(k)
                        else next.add(k)
                        return next
                      })
                    }}
                    title={t.description || t.key}
                  >
                    {isExpanded ? '▾' : '▸'} {t.title}
                  </button>
                  {items.length > 0 && isExpanded ? (
                    <div className="nav-sub">
                      {items.map((d) => (
                        <button
                          key={d.id}
                          type="button"
                          className={`nav-item sub ${selected?.doc.id === d.id ? 'active' : ''}`}
                          onClick={() => {
                            setTypeFilter({ mode: 'type', typeId: t.id })
                            selectDoc(d)
                          }}
                          title={d.id}
                        >
                          {d.title}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        </section>

        <section className="card">
          <h2 className="h2">Документы — {selectedTypeTitle}</h2>
          {loading ? (
            <div className="muted">Загрузка…</div>
          ) : visibleDocs.length === 0 ? (
            <div className="muted">Пока нет документов</div>
          ) : (
            <div className="table">
              <div className="table-head">
                <div>Название</div>
                <div className="only-wide">Создан</div>
                <div>Последняя версия</div>
              </div>
              {visibleDocs.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  className={`table-row ${selected?.doc.id === d.id ? 'active' : ''}`}
                  onClick={() => selectDoc(d)}
                >
                  <div className="cell-main">
                    <div className="cell-title">{d.title}</div>
                    <div className="cell-sub muted">{d.id}</div>
                  </div>
                  <div className="only-wide muted">{new Date(d.created_at).toLocaleString()}</div>
                  <div className="muted">{d.latest_version_id ? d.latest_version_content_type || 'version' : '—'}</div>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>

      {selected ? (
        <section className="card">
          <h2 className="h2">Версии: {selected.doc.title}</h2>
          {selected.versions.length === 0 ? (
            <div className="muted">Нет версий</div>
          ) : (
            <div className="stack">
              {selected.versions.map((v) => (
                <div key={v.id} className="row row-space row-wrap">
                  <div className="stack-tight">
                    <div className="cell-title">{new Date(v.created_at).toLocaleString()}</div>
                    <div className="muted">{v.content_type}</div>
                    <div className="muted">{v.id}</div>
                  </div>
                  <div className="row">
                    <button
                      className="btn"
                      type="button"
                      onClick={() => loadPreview(v)}
                      aria-pressed={selectedVersionId === v.id}
                    >
                      Открыть
                    </button>
                    <button
                      className="btn"
                      type="button"
                      onClick={async () => {
                        try {
                          const blob = await downloadVersionArtifactBlob(v.id)
                          const objUrl = URL.createObjectURL(blob)
                          const a = document.createElement('a')
                          a.href = objUrl
                          a.download = `version-${v.id}.txt`
                          document.body.appendChild(a)
                          a.click()
                          a.remove()
                          setTimeout(() => URL.revokeObjectURL(objUrl), 1000)
                        } catch (e: any) {
                          setError(e?.message || 'Не удалось скачать')
                        }
                      }}
                    >
                      Скачать
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      ) : (
        <section className="card">
          <div className="muted">Выберите документ, чтобы увидеть версии.</div>
        </section>
      )}

    </div>
  )
}

function EntitiesPanel(props: {
  selected: Selection | null
  selectedVersionId: string | null
  applyingEntities: boolean
  entityFields: EntityFields
  onChangeEntityFields: (next: EntityFields | ((prev: EntityFields) => EntityFields)) => void
  createTitle: string
  createText: string
  creating: boolean
  onChangeTitle: (v: string) => void
  onChangeText: (v: string) => void
  onChangeFile: (f: File | null) => void
  onCreate: () => void
  onApplyEntitiesToDocument: () => void

  addText: string
  adding: boolean
  onChangeAddText: (v: string) => void
  onChangeAddFile: (f: File | null) => void
  onAddVersion: () => void
}) {
  return (
    <div className="stack">
      <section className="card">
        <h2 className="h2">Выбор</h2>
        {props.selected ? (
          <div className="stack-tight">
            <div className="cell-title">{props.selected.doc.title}</div>
            <div className="muted">doc_id: {props.selected.doc.id}</div>
            <div className="muted">version_id: {props.selectedVersionId || '—'}</div>
          </div>
        ) : (
          <div className="muted">Документ не выбран.</div>
        )}

        <div className="divider" />

        <h3 className="h3">Создать документ</h3>
        <div className="form-grid">
          <label className="field">
            <span className="field-label">Название</span>
            <input value={props.createTitle} onChange={(e) => props.onChangeTitle(e.target.value)} />
          </label>

          <label className="field">
            <span className="field-label">Файл (опционально)</span>
            <input
              type="file"
              onChange={(e) => props.onChangeFile(e.target.files?.[0] || null)}
              aria-label="Загрузить файл"
            />
          </label>

          <label className="field">
            <span className="field-label">Текст (если без файла)</span>
            <textarea
              rows={6}
              value={props.createText}
              onChange={(e) => props.onChangeText(e.target.value)}
              placeholder="Вставьте текст договора"
            />
          </label>

          <button className="btn" type="button" onClick={props.onCreate} disabled={props.creating}>
            {props.creating ? 'Создаю…' : 'Создать'}
          </button>
        </div>
      </section>

      <section className="card">
        <h2 className="h2">Редактор сущностей</h2>
        <div className="form-grid">
          <div className="muted">
            Заполните поля — они подставятся в документ в правильной форме, если в тексте есть плейсхолдеры.
            <br />
            <span>
              Примеры: {'{{customer.requisites}}'}, {'{{executor.requisites}}'}, {'{{customer.contacts}}'}, {'{{object.summary}}'}, {'{{project.brief}}'} — и другие.
            </span>
          </div>

          <h3 className="h3">Заказчик</h3>
          <label className="field">
            <span className="field-label">Статус</span>
            <select
              value={props.entityFields.customer_status}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({
                  ...prev,
                  customer_status: e.target.value as EntityFields['customer_status'],
                }))
              }
            >
              <option value="person">Физлицо</option>
              <option value="ip">ИП</option>
              <option value="self_employed">Самозанятый</option>
              <option value="company">Юрлицо</option>
            </select>
          </label>
          <label className="field">
            <span className="field-label">ФИО</span>
            <input
              value={props.entityFields.customer_fio}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, customer_fio: e.target.value }))
              }
              placeholder="Иванов Иван Иванович"
            />
          </label>
          <label className="field">
            <span className="field-label">ИНН (если есть)</span>
            <input
              value={props.entityFields.customer_inn}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, customer_inn: e.target.value }))}
              placeholder="770000000000"
            />
          </label>
          <label className="field">
            <span className="field-label">Адрес</span>
            <input
              value={props.entityFields.customer_address}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, customer_address: e.target.value }))
              }
              placeholder="г. Москва, ул. …"
            />
          </label>
          <label className="field">
            <span className="field-label">Телефон</span>
            <input
              value={props.entityFields.customer_phone}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, customer_phone: e.target.value }))
              }
              placeholder="+7 …"
            />
          </label>
          <label className="field">
            <span className="field-label">Email</span>
            <input
              value={props.entityFields.customer_email}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, customer_email: e.target.value }))
              }
              placeholder="name@example.com"
            />
          </label>
          <label className="field">
            <span className="field-label">Telegram</span>
            <input
              value={props.entityFields.customer_telegram}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, customer_telegram: e.target.value }))}
              placeholder="@username"
            />
          </label>
          <label className="field">
            <span className="field-label">WhatsApp</span>
            <input
              value={props.entityFields.customer_whatsapp}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, customer_whatsapp: e.target.value }))}
              placeholder="+7 … или ссылка"
            />
          </label>

          <h3 className="h3">Исполнитель</h3>
          <label className="field">
            <span className="field-label">Наименование</span>
            <input
              value={props.entityFields.executor_name}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, executor_name: e.target.value }))
              }
              placeholder='ООО "Пример Дизайн"'
            />
          </label>
          <label className="field">
            <span className="field-label">Адрес</span>
            <input
              value={props.entityFields.executor_address}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, executor_address: e.target.value }))
              }
            />
          </label>
          <label className="field">
            <span className="field-label">ИНН</span>
            <input
              value={props.entityFields.executor_inn}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, executor_inn: e.target.value }))
            }
              placeholder="7700000000"
            />
          </label>
          <label className="field">
            <span className="field-label">Телефон</span>
            <input
              value={props.entityFields.executor_phone}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, executor_phone: e.target.value }))}
              placeholder="+7 …"
            />
          </label>
          <label className="field">
            <span className="field-label">Email</span>
            <input
              value={props.entityFields.executor_email}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, executor_email: e.target.value }))}
              placeholder="info@example.com"
            />
          </label>
          <label className="field">
            <span className="field-label">Telegram</span>
            <input
              value={props.entityFields.executor_telegram}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, executor_telegram: e.target.value }))}
              placeholder="@company_support"
            />
          </label>

          <h3 className="h3">Объект</h3>
          <label className="field">
            <span className="field-label">Адрес объекта</span>
            <input
              value={props.entityFields.object_address}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, object_address: e.target.value }))
              }
            />
          </label>

          <label className="field">
            <span className="field-label">Тип объекта</span>
            <select
              value={props.entityFields.object_type}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({
                  ...prev,
                  object_type: e.target.value as EntityFields['object_type'],
                }))
              }
            >
              <option value="apartment">Квартира</option>
              <option value="house">Дом</option>
              <option value="commercial">Коммерческий объект</option>
              <option value="other">Другое</option>
            </select>
          </label>

          <label className="field">
            <span className="field-label">Количество комнат</span>
            <input
              value={props.entityFields.object_rooms_count}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, object_rooms_count: e.target.value }))}
              placeholder="2"
              inputMode="numeric"
            />
          </label>

          <label className="field">
            <span className="field-label">Площадь (м²)</span>
            <input
              value={props.entityFields.object_area_sqm}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, object_area_sqm: e.target.value }))}
              placeholder="54.3"
              inputMode="decimal"
            />
          </label>

          <label className="field">
            <span className="field-label">Высота потолков (м)</span>
            <input
              value={props.entityFields.object_ceiling_height_m}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, object_ceiling_height_m: e.target.value }))
              }
              placeholder="2.7"
              inputMode="decimal"
            />
          </label>

          <div className="row row-wrap">
            <label className="field" style={{ flex: 1, minWidth: 120 }}>
              <span className="field-label">Этаж</span>
              <input
                value={props.entityFields.object_floor}
                onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, object_floor: e.target.value }))}
                placeholder="7"
                inputMode="numeric"
              />
            </label>
            <label className="field" style={{ flex: 1, minWidth: 120 }}>
              <span className="field-label">Этажность</span>
              <input
                value={props.entityFields.object_floors_total}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, object_floors_total: e.target.value }))
                }
                placeholder="17"
                inputMode="numeric"
              />
            </label>
          </div>

          <label className="field">
            <span className="field-label">Санузлов</span>
            <input
              value={props.entityFields.object_bathrooms_count}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, object_bathrooms_count: e.target.value }))
              }
              placeholder="1"
              inputMode="numeric"
            />
          </label>

          <label className="field">
            <span className="field-label">Балкон/лоджия</span>
            <select
              value={props.entityFields.object_has_balcony}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({
                  ...prev,
                  object_has_balcony: e.target.value as EntityFields['object_has_balcony'],
                }))
              }
            >
              <option value="no">Нет</option>
              <option value="yes">Есть</option>
            </select>
          </label>

          <label className="field">
            <span className="field-label">Список помещений (через запятую или с новой строки)</span>
            <textarea
              rows={4}
              value={props.entityFields.object_rooms_list}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, object_rooms_list: e.target.value }))}
              placeholder="Кухня\nГостиная\nСпальня\nСанузел"
            />
          </label>

          <div className="row row-wrap">
            <label className="field" style={{ flex: 1, minWidth: 120 }}>
              <span className="field-label">Количество проживающих</span>
              <input
                value={props.entityFields.object_residents_count}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, object_residents_count: e.target.value }))
                }
                placeholder="2"
                inputMode="numeric"
              />
            </label>
            <label className="field" style={{ flex: 1, minWidth: 120 }}>
              <span className="field-label">Домашние животные</span>
              <select
                value={props.entityFields.object_has_pets}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({
                    ...prev,
                    object_has_pets: e.target.value as EntityFields['object_has_pets'],
                  }))
                }
              >
                <option value="no">Нет</option>
                <option value="yes">Есть</option>
              </select>
            </label>
          </div>

          <label className="field">
            <span className="field-label">Животные (если есть)</span>
            <input
              value={props.entityFields.object_pets_notes}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, object_pets_notes: e.target.value }))}
              placeholder="Кошка, собака средняя, аллергии…"
            />
          </label>

          <h3 className="h3">Дизайн‑проект</h3>

          <label className="field">
            <span className="field-label">Объём работ</span>
            <select
              value={props.entityFields.project_scope}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({
                  ...prev,
                  project_scope: e.target.value as EntityFields['project_scope'],
                }))
              }
            >
              <option value="full">Дизайн‑проект под ключ</option>
              <option value="rooms_only">Отдельные помещения</option>
              <option value="consultation">Консультация</option>
              <option value="other">Другое</option>
            </select>
          </label>

          <label className="field">
            <span className="field-label">Стиль / пожелания</span>
            <input
              value={props.entityFields.project_style}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, project_style: e.target.value }))}
              placeholder="Современный, минимализм…"
            />
          </label>

          <label className="field">
            <span className="field-label">Тип ремонта / исходное состояние</span>
            <select
              value={props.entityFields.project_renovation_type}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({
                  ...prev,
                  project_renovation_type: e.target.value as EntityFields['project_renovation_type'],
                }))
              }
            >
              <option value="new_build">Новостройка</option>
              <option value="secondary">Вторичка</option>
              <option value="cosmetic">Косметический ремонт</option>
              <option value="capital">Капитальный ремонт</option>
              <option value="other">Другое</option>
            </select>
          </label>

          <label className="field">
            <span className="field-label">Бюджет (текстом)</span>
            <input
              value={props.entityFields.project_budget}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, project_budget: e.target.value }))}
              placeholder="например: до 3 000 000 ₽ на ремонт"
            />
          </label>

          <label className="field">
            <span className="field-label">Цена за м² (₽/м²)</span>
            <input
              value={props.entityFields.project_price_per_sqm}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({
                  ...prev,
                  project_price_per_sqm: e.target.value,
                }))
              }
              placeholder="например: 3500"
            />
          </label>

          <label className="field">
            <span className="field-label">Итоговая стоимость услуг (₽)</span>
            <input
              value={props.entityFields.project_price_total}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, project_price_total: e.target.value }))}
              placeholder="например: 175000"
            />
            {(() => {
              const computed = computedProjectPrice(props.entityFields)
              if (!computed) return null
              const area = withUnit(String(computed.area), 'м²')
              const rate = `${new Intl.NumberFormat('ru-RU').format(Math.round(computed.rate))} ₽/м²`
              return (
                <div className="muted" style={{ marginTop: 6 }}>
                  Авто‑расчёт: {formatRub(computed.total)} ({rate} × {area})
                </div>
              )
            })()}
          </label>

          <label className="field">
            <span className="field-label">Порядок оплаты</span>
            <textarea
              rows={3}
              value={props.entityFields.project_payment_terms}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, project_payment_terms: e.target.value }))}
              placeholder="например: 50% аванс, 50% по сдаче альбома"
            />
          </label>

          <h3 className="h3">Методы оплаты</h3>
          <div className="form-grid">
            <label className="row row-check">
              <span>Наличные</span>
              <input
                type="checkbox"
                checked={props.entityFields.payment_method_cash}
                onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, payment_method_cash: e.target.checked }))}
              />
            </label>
            <label className="row row-check">
              <span>Безналичный перевод</span>
              <input
                type="checkbox"
                checked={props.entityFields.payment_method_bank_transfer}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, payment_method_bank_transfer: e.target.checked }))
                }
              />
            </label>
            <label className="row row-check">
              <span>Карта</span>
              <input
                type="checkbox"
                checked={props.entityFields.payment_method_card}
                onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, payment_method_card: e.target.checked }))}
              />
            </label>
            <label className="row row-check">
              <span>СБП</span>
              <input
                type="checkbox"
                checked={props.entityFields.payment_method_sbp}
                onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, payment_method_sbp: e.target.checked }))}
              />
            </label>
          </div>

          <label className="field">
            <span className="field-label">Другой метод оплаты (опционально)</span>
            <input
              value={props.entityFields.payment_method_other}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, payment_method_other: e.target.value }))}
              placeholder="например: оплата по ссылке, QR…"
            />
          </label>

          <label className="field">
            <span className="field-label">Сроки (текстом)</span>
            <input
              value={props.entityFields.project_deadline}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, project_deadline: e.target.value }))}
              placeholder="например: старт 10.02.2026, сдача до 01.04.2026"
            />
          </label>

          <div className="row row-wrap">
            <label className="field" style={{ flex: 1, minWidth: 120 }}>
              <span className="field-label">Правки включены</span>
              <input
                value={props.entityFields.project_revisions_included}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, project_revisions_included: e.target.value }))
                }
                placeholder="например: 2 итерации"
              />
            </label>
            <label className="field" style={{ flex: 1, minWidth: 120 }}>
              <span className="field-label">Авторский надзор</span>
              <select
                value={props.entityFields.project_author_supervision}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({
                    ...prev,
                    project_author_supervision: e.target.value as EntityFields['project_author_supervision'],
                  }))
                }
              >
                <option value="no">Нет</option>
                <option value="yes">Да</option>
              </select>
            </label>
          </div>

          <label className="field">
            <span className="field-label">Доп. правки (стоимость/условия)</span>
            <input
              value={props.entityFields.project_revision_extra_terms}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, project_revision_extra_terms: e.target.value }))
              }
              placeholder="например: 1 500 ₽/итерация после включённых"
            />
          </label>

          <label className="field">
            <span className="field-label">Количество выездов/встреч (если важно)</span>
            <input
              value={props.entityFields.project_site_visits_count}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, project_site_visits_count: e.target.value }))}
              placeholder="например: 3"
              inputMode="numeric"
            />
          </label>

          <label className="field">
            <span className="field-label">Кто оплачивает выезды</span>
            <select
              value={props.entityFields.project_site_visits_paid_by}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({
                  ...prev,
                  project_site_visits_paid_by: e.target.value as EntityFields['project_site_visits_paid_by'],
                }))
              }
            >
              <option value="customer">Заказчик</option>
              <option value="executor">Исполнитель</option>
              <option value="split">Поровну/по договорённости</option>
              <option value="other">Другое</option>
            </select>
          </label>

          <label className="field">
            <span className="field-label">Уточнение по выездам (опционально)</span>
            <input
              value={props.entityFields.project_site_visits_paid_by_details}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, project_site_visits_paid_by_details: e.target.value }))
              }
              placeholder="например: 1-й выезд включён, дальше оплачивает заказчик"
            />
          </label>

          <label className="field">
            <span className="field-label">Расходы на выезды (транспорт/парковка)</span>
            <input
              value={props.entityFields.project_site_visits_expenses}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, project_site_visits_expenses: e.target.value }))
              }
              placeholder="например: компенсируются по чекам"
            />
          </label>

          <h3 className="h3">Закупки / комплектация</h3>

          <label className="field">
            <span className="field-label">Кто оплачивает закупки (материалы/мебель/оборудование)</span>
            <select
              value={props.entityFields.project_procurement_buys_paid_by}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({
                  ...prev,
                  project_procurement_buys_paid_by: e.target.value as EntityFields['project_procurement_buys_paid_by'],
                }))
              }
            >
              <option value="customer">Заказчик</option>
              <option value="executor">Исполнитель</option>
              <option value="split">Поровну/по договорённости</option>
              <option value="other">Другое</option>
            </select>
          </label>
          <label className="field">
            <span className="field-label">Уточнение по закупкам (опционально)</span>
            <input
              value={props.entityFields.project_procurement_buys_details}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, project_procurement_buys_details: e.target.value }))
              }
              placeholder="например: закупки по согласованной спецификации, оплата напрямую поставщикам"
            />
          </label>

          <label className="field">
            <span className="field-label">Кто принимает доставки</span>
            <select
              value={props.entityFields.project_procurement_delivery_acceptance_by}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({
                  ...prev,
                  project_procurement_delivery_acceptance_by: e.target.value as EntityFields['project_procurement_delivery_acceptance_by'],
                }))
              }
            >
              <option value="customer">Заказчик</option>
              <option value="executor">Исполнитель</option>
              <option value="split">Поровну/по договорённости</option>
              <option value="other">Другое</option>
            </select>
          </label>
          <label className="field">
            <span className="field-label">Уточнение по доставкам (опционально)</span>
            <input
              value={props.entityFields.project_procurement_delivery_acceptance_details}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, project_procurement_delivery_acceptance_details: e.target.value }))
              }
              placeholder="например: заказчик принимает и подписывает ТТН, дизайнер присутствует на ключевых поставках"
            />
          </label>

          <label className="field">
            <span className="field-label">Кто оплачивает подъём/сборку/монтаж</span>
            <select
              value={props.entityFields.project_procurement_lifting_assembly_paid_by}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({
                  ...prev,
                  project_procurement_lifting_assembly_paid_by: e.target.value as EntityFields['project_procurement_lifting_assembly_paid_by'],
                }))
              }
            >
              <option value="customer">Заказчик</option>
              <option value="executor">Исполнитель</option>
              <option value="split">Поровну/по договорённости</option>
              <option value="other">Другое</option>
            </select>
          </label>
          <label className="field">
            <span className="field-label">Уточнение по подъёму/сборке (опционально)</span>
            <input
              value={props.entityFields.project_procurement_lifting_assembly_details}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, project_procurement_lifting_assembly_details: e.target.value }))
              }
              placeholder="например: по чекам/сметам подрядчиков, оплачивает заказчик"
            />
          </label>

          <label className="field">
            <span className="field-label">Кто оплачивает хранение/складирование (если нужно)</span>
            <select
              value={props.entityFields.project_procurement_storage_paid_by}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({
                  ...prev,
                  project_procurement_storage_paid_by: e.target.value as EntityFields['project_procurement_storage_paid_by'],
                }))
              }
            >
              <option value="customer">Заказчик</option>
              <option value="executor">Исполнитель</option>
              <option value="split">Поровну/по договорённости</option>
              <option value="other">Другое</option>
            </select>
          </label>
          <label className="field">
            <span className="field-label">Уточнение по хранению (опционально)</span>
            <input
              value={props.entityFields.project_procurement_storage_details}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, project_procurement_storage_details: e.target.value }))
              }
              placeholder="например: при необходимости склад оплачивает заказчик"
            />
          </label>

          <h3 className="h3">Согласование / сроки / ответственность</h3>
          <label className="field">
            <span className="field-label">Согласование (SLA по ответам)</span>
            <input
              value={props.entityFields.project_approval_sla}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, project_approval_sla: e.target.value }))}
              placeholder="например: заказчик отвечает в течение 2 рабочих дней"
            />
          </label>
          <label className="field">
            <span className="field-label">Сдвиг сроков при задержках согласования</span>
            <input
              value={props.entityFields.project_deadline_shift_terms}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, project_deadline_shift_terms: e.target.value }))
              }
              placeholder="например: сроки сдвигаются на фактическое время просрочки согласования"
            />
          </label>
          <label className="field">
            <span className="field-label">Штрафы / ответственность (опционально)</span>
            <input
              value={props.entityFields.project_penalties_terms}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, project_penalties_terms: e.target.value }))
              }
              placeholder="например: без штрафов; или 0.1%/день при просрочке по вине исполнителя"
            />
          </label>

          <label className="field">
            <span className="field-label">Формат передачи результата</span>
            <input
              value={props.entityFields.project_handover_format}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, project_handover_format: e.target.value }))}
              placeholder="PDF + исходники (DWG), ссылка на облако"
            />
          </label>

          <div className="row row-wrap">
            <label className="field" style={{ flex: 1, minWidth: 120 }}>
              <span className="field-label">Канал связи</span>
              <select
                value={props.entityFields.project_communication_channel}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({
                    ...prev,
                    project_communication_channel: e.target.value as EntityFields['project_communication_channel'],
                  }))
                }
              >
                <option value="telegram">Telegram</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="email">Email</option>
                <option value="phone">Телефон</option>
                <option value="other">Другое</option>
              </select>
            </label>
            <label className="field" style={{ flex: 2, minWidth: 180 }}>
              <span className="field-label">Детали канала связи</span>
              <input
                value={props.entityFields.project_communication_details}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, project_communication_details: e.target.value }))
                }
                placeholder="@username или номер/почта"
              />
            </label>
          </div>

          <label className="field">
            <span className="field-label">Правила связи (время ответа/часы)</span>
            <input
              value={props.entityFields.project_communication_rules}
              onChange={(e) =>
                props.onChangeEntityFields((prev) => ({ ...prev, project_communication_rules: e.target.value }))
              }
              placeholder="например: ответ в течение 1 рабочего дня, 10:00–19:00"
            />
          </label>

          <h3 className="h3">Состав результата</h3>
          <div className="form-grid">
            <label className="row row-check">
              <span>Обмерный план</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_measurements}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, deliverable_measurements: e.target.checked }))
                }
              />
            </label>
            <label className="row row-check">
              <span>Планировочное решение</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_plan_solution}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, deliverable_plan_solution: e.target.checked }))
                }
              />
            </label>
            <label className="row row-check">
              <span>План демонтажа</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_demolition_plan}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, deliverable_demolition_plan: e.target.checked }))
                }
              />
            </label>
            <label className="row row-check">
              <span>План монтажа/перегородок</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_construction_plan}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, deliverable_construction_plan: e.target.checked }))
                }
              />
            </label>
            <label className="row row-check">
              <span>План электрики</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_electric_plan}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, deliverable_electric_plan: e.target.checked }))
                }
              />
            </label>
            <label className="row row-check">
              <span>План сантехники</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_plumbing_plan}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, deliverable_plumbing_plan: e.target.checked }))
                }
              />
            </label>
            <label className="row row-check">
              <span>План освещения</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_lighting_plan}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, deliverable_lighting_plan: e.target.checked }))
                }
              />
            </label>
            <label className="row row-check">
              <span>План потолков</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_ceiling_plan}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, deliverable_ceiling_plan: e.target.checked }))
                }
              />
            </label>
            <label className="row row-check">
              <span>План полов</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_floor_plan}
                onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, deliverable_floor_plan: e.target.checked }))}
              />
            </label>
            <label className="row row-check">
              <span>План мебели/расстановки</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_furniture_plan}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, deliverable_furniture_plan: e.target.checked }))
                }
              />
            </label>
            <label className="row row-check">
              <span>Ведомость отделки</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_finishes_schedule}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, deliverable_finishes_schedule: e.target.checked }))
                }
              />
            </label>
            <label className="row row-check">
              <span>Спецификация</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_specification}
                onChange={(e) =>
                  props.onChangeEntityFields((prev) => ({ ...prev, deliverable_specification: e.target.checked }))
                }
              />
            </label>
            <label className="row row-check">
              <span>3D‑визуализации</span>
              <input
                type="checkbox"
                checked={props.entityFields.deliverable_3d_visuals}
                onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, deliverable_3d_visuals: e.target.checked }))}
              />
            </label>
          </div>

          <label className="field">
            <span className="field-label">Примечания</span>
            <textarea
              rows={4}
              value={props.entityFields.project_notes}
              onChange={(e) => props.onChangeEntityFields((prev) => ({ ...prev, project_notes: e.target.value }))}
              placeholder="Пожелания, ограничения, состав семьи, домашние животные и т.д."
            />
          </label>

          <div className="divider" />
          <button
            className="btn"
            type="button"
            onClick={props.onApplyEntitiesToDocument}
            disabled={!props.selected || props.applyingEntities}
            title="Создаёт новую текстовую версию с подставленными значениями"
          >
            {props.applyingEntities ? 'Подставляю…' : 'Подставить в документ (новая версия)'}
          </button>
        </div>
      </section>

      <section className="card">
        <h2 className="h2">Генерация</h2>
        <div className="stack-tight">
          <button className="btn" type="button" disabled>
            Выбрать генератор (скоро)
          </button>
          <button className="btn" type="button" disabled>
            Сгенерировать (скоро)
          </button>
        </div>
      </section>

      <section className="card">
        <h2 className="h2">Добавить версию</h2>
        {props.selected ? (
          <div className="form-grid">
            <label className="field">
              <span className="field-label">Файл (опционально)</span>
              <input
                type="file"
                onChange={(e) => props.onChangeAddFile(e.target.files?.[0] || null)}
                aria-label="Загрузить новую версию"
              />
            </label>

            <label className="field">
              <span className="field-label">Текст (если без файла)</span>
              <textarea
                rows={6}
                value={props.addText}
                onChange={(e) => props.onChangeAddText(e.target.value)}
                placeholder="Вставьте новый текст версии"
              />
            </label>

            <button className="btn" type="button" onClick={props.onAddVersion} disabled={props.adding}>
              {props.adding ? 'Добавляю…' : 'Добавить версию'}
            </button>
          </div>
        ) : (
          <div className="muted">Выберите документ</div>
        )}
      </section>
    </div>
  )
}
