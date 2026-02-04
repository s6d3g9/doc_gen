export type DocumentIndexItem = {
  id: string
  title: string
  created_at: string
  type_id?: string | null
  latest_version_id: string | null
  latest_version_created_at: string | null
  latest_version_content_type: string | null
}

export type DocumentType = {
  id: string
  key: string
  title: string
  description: string | null
  created_at: string
  updated_at: string
}

export type DocumentVersion = {
  id: string
  document_id: string
  created_at: string
  artifact_path: string
  content_type: string
}

export type DocumentCreateResponse = {
  document: {
    id: string
    title: string
    created_at: string
  }
  version: DocumentVersion
}

export type AIGenerateTemplateResponse = {
  text: string
  task_id?: string | null
}

export type AIExtractEntitiesResponse = {
  data: Record<string, any>
  raw_text: string
}

export type AIChatMessage = {
  role: 'user' | 'assistant'
  text: string
}

export type AIChatResponse = {
  text: string
}

export type GoogleStatusResponse = {
  connected: boolean
  email?: string | null
}

export type SaveToGoogleDocsResponse = {
  drive_file_id: string
  web_view_link?: string | null
}

export type AuthRegisterResponse = {
  access_token: string
  seed_phrase: string
}

export type AuthTokenResponse = {
  access_token: string
}

export type AuthMeResponse = {
  id: string
  email: string
  created_at: string
}

export type OpenRouterModel = {
  id: string
  name?: string | null
  context_length?: number | null
}

export type OpenRouterConfig = {
  provider: string
  base_url: string
  model?: string | null
  has_api_key: boolean
  active_key_id?: string | null
  keys_count?: number
}

export type OpenRouterKey = {
  id: string
  label?: string | null
  created_at: string
  is_active: boolean
}

let _authToken: string | null = null

export function setAuthToken(token: string | null) {
  _authToken = token
}

function authHeader(): Record<string, string> {
  return _authToken ? { Authorization: `Bearer ${_authToken}` } : {}
}

function baseUrl() {
  return (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000'
}

function url(path: string) {
  const b = baseUrl().replace(/\/$/, '')
  return path.startsWith('http') ? path : `${b}${path.startsWith('/') ? '' : '/'}${path}`
}

export async function listDocumentsIndex(): Promise<DocumentIndexItem[]> {
  const resp = await fetch(url('/documents/index'), { headers: { ...authHeader() } })
  if (!resp.ok) throw new Error(`Failed to load documents: ${resp.status}`)
  return await resp.json()
}

export async function listDocumentTypes(): Promise<DocumentType[]> {
  const resp = await fetch(url('/document-types'))
  if (!resp.ok) throw new Error(`Failed to load document types: ${resp.status}`)
  return await resp.json()
}

export async function createDocumentFromText(
  title: string,
  text: string,
  typeId?: string | null,
): Promise<DocumentCreateResponse> {
  const fd = new FormData()
  fd.set('title', title)
  fd.set('text', text)
  if (typeId) fd.set('type_id', typeId)

  const resp = await fetch(url('/documents'), {
    method: 'POST',
    headers: { ...authHeader() },
    body: fd,
  })
  if (!resp.ok) throw new Error(`Failed to create document: ${resp.status}`)
  return await resp.json()
}

export async function createDocumentFromFile(
  title: string,
  file: File,
  typeId?: string | null,
): Promise<DocumentCreateResponse> {
  const fd = new FormData()
  fd.set('title', title)
  fd.set('file', file)
  if (typeId) fd.set('type_id', typeId)

  const resp = await fetch(url('/documents'), {
    method: 'POST',
    headers: { ...authHeader() },
    body: fd,
  })
  if (!resp.ok) throw new Error(`Failed to create document: ${resp.status}`)
  return await resp.json()
}

export async function listDocumentVersions(documentId: string): Promise<DocumentVersion[]> {
  const resp = await fetch(url(`/documents/${documentId}/versions`), { headers: { ...authHeader() } })
  if (!resp.ok) throw new Error(`Failed to load versions: ${resp.status}`)
  return await resp.json()
}

export async function addVersionFromText(documentId: string, text: string): Promise<DocumentVersion> {
  const fd = new FormData()
  fd.set('text', text)

  const resp = await fetch(url(`/documents/${documentId}/versions`), {
    method: 'POST',
    headers: { ...authHeader() },
    body: fd,
  })
  if (!resp.ok) throw new Error(`Failed to add version: ${resp.status}`)
  return await resp.json()
}

export async function addVersionFromFile(documentId: string, file: File): Promise<DocumentVersion> {
  const fd = new FormData()
  fd.set('file', file)

  const resp = await fetch(url(`/documents/${documentId}/versions`), {
    method: 'POST',
    headers: { ...authHeader() },
    body: fd,
  })
  if (!resp.ok) throw new Error(`Failed to add version: ${resp.status}`)
  return await resp.json()
}

export async function fetchVersionArtifactText(versionId: string): Promise<string> {
  const resp = await fetch(url(`/documents/versions/${versionId}/artifact`), { headers: { ...authHeader() } })
  if (!resp.ok) throw new Error(`Failed to download artifact: ${resp.status}`)
  return await resp.text()
}

export function downloadUrlForVersionArtifact(versionId: string) {
  return url(`/documents/versions/${versionId}/artifact`)
}

export async function downloadVersionArtifactBlob(versionId: string): Promise<Blob> {
  const resp = await fetch(url(`/documents/versions/${versionId}/artifact`), { headers: { ...authHeader() } })
  if (!resp.ok) throw new Error(`Failed to download artifact: ${resp.status}`)
  return await resp.blob()
}

export async function aiGenerateTemplate(args: {
  base_text?: string | null
  instructions?: string | null
  entities?: Record<string, any>
}): Promise<AIGenerateTemplateResponse> {
  const resp = await fetch(url('/ai/generate-template'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({
      base_text: args.base_text || null,
      instructions: args.instructions || null,
      entities: args.entities || {},
    }),
  })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to generate template: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function aiExtractEntities(args: {
  version_id: string
  instructions?: string | null
}): Promise<AIExtractEntitiesResponse> {
  const resp = await fetch(url('/ai/extract-entities'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({
      version_id: args.version_id,
      instructions: args.instructions || null,
    }),
  })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to extract entities: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function aiChat(args: {
  version_id?: string | null
  messages: AIChatMessage[]
}): Promise<AIChatResponse> {
  const resp = await fetch(url('/ai/chat'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({
      version_id: args.version_id ?? null,
      messages: args.messages || [],
    }),
  })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to chat: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function googleStatus(): Promise<GoogleStatusResponse> {
  const resp = await fetch(url('/google/status'))
  if (!resp.ok) throw new Error(`Failed to load google status: ${resp.status}`)
  return await resp.json()
}

export async function googleLogout(): Promise<{ ok: boolean }> {
  const resp = await fetch(url('/google/logout'), { method: 'POST' })
  if (!resp.ok) throw new Error(`Failed to logout: ${resp.status}`)
  return await resp.json()
}

export function googleLoginUrl(returnTo: string) {
  return url(`/google/login?return_to=${encodeURIComponent(returnTo)}`)
}

export async function saveToGoogleDocs(args: {
  version_id: string
  title?: string | null
  text?: string | null
}): Promise<SaveToGoogleDocsResponse> {
  const resp = await fetch(url('/google/docs/save'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({
      version_id: args.version_id,
      title: args.title || null,
      text: args.text ?? null,
    }),
  })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to save to Google Docs: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function authRegister(args: { email: string; password: string }): Promise<AuthRegisterResponse> {
  const resp = await fetch(url('/auth/register'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args),
  })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to register: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function authLoginEmail(args: { email: string; password: string }): Promise<AuthTokenResponse> {
  const resp = await fetch(url('/auth/login/email'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args),
  })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to login: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function authLoginSeed(args: { seed_phrase: string }): Promise<AuthTokenResponse> {
  const resp = await fetch(url('/auth/login/seed'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args),
  })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to login by seed: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function authMe(): Promise<AuthMeResponse> {
  const resp = await fetch(url('/auth/me'), {
    headers: { ...authHeader() },
  })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to load me: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function listOpenRouterModels(): Promise<OpenRouterModel[]> {
  const resp = await fetch(url('/ai/openrouter/models'))
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to load models: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function getOpenRouterConfig(): Promise<OpenRouterConfig> {
  const resp = await fetch(url('/ai/openrouter/config'), { headers: { ...authHeader() } })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to load AI config: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function setOpenRouterConfig(args: { api_key?: string | null; model?: string | null }): Promise<OpenRouterConfig> {
  const resp = await fetch(url('/ai/openrouter/config'), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({
      api_key: args.api_key ?? null,
      model: args.model ?? null,
    }),
  })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to save AI config: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function listOpenRouterKeys(): Promise<OpenRouterKey[]> {
  const resp = await fetch(url('/ai/openrouter/keys'), { headers: { ...authHeader() } })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to load API keys: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function createOpenRouterKey(args: { api_key: string; label?: string | null }): Promise<OpenRouterKey> {
  const resp = await fetch(url('/ai/openrouter/keys'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({ api_key: args.api_key, label: args.label ?? null }),
  })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to add API key: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function deleteOpenRouterKey(keyId: string): Promise<{ ok: boolean }> {
  const resp = await fetch(url(`/ai/openrouter/keys/${encodeURIComponent(keyId)}`), {
    method: 'DELETE',
    headers: { ...authHeader() },
  })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to delete API key: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}

export async function setOpenRouterActive(args: {
  active_key_id?: string | null
  model?: string | null
  api_key?: string | null
  label?: string | null
}): Promise<OpenRouterConfig> {
  const resp = await fetch(url('/ai/openrouter/config'), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({
      active_key_id: args.active_key_id ?? null,
      model: args.model ?? null,
      api_key: args.api_key ?? null,
      label: args.label ?? null,
    }),
  })
  if (!resp.ok) {
    const t = await resp.text().catch(() => '')
    throw new Error(`Failed to save AI config: ${resp.status}${t ? ` — ${t}` : ''}`)
  }
  return await resp.json()
}
