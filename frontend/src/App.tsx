import React, { useMemo, useState } from 'react'
import { useTheme } from './theme'
import DocumentsScreen from './screens/DocumentsScreen'
import { PropertiesOutlet, PropertiesProvider } from './layout/PropertiesSlot'
import {
  authLoginEmail,
  authLoginSeed,
  authMe,
  authRegister,
  getOpenRouterConfig,
  listOpenRouterModels,
  setAuthToken,
  setOpenRouterConfig,
  type AuthMeResponse,
  type OpenRouterModel,
} from './api'

function useIsNarrow() {
  const [isNarrow, setIsNarrow] = useState(() => window.matchMedia('(max-width: 900px)').matches)

  React.useEffect(() => {
    const mq = window.matchMedia('(max-width: 900px)')
    const handler = () => setIsNarrow(mq.matches)
    handler()

    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  return isNarrow
}

export default function App() {
  const { mode, setMode } = useTheme()
  const isNarrow = useIsNarrow()
  const [propsOpen, setPropsOpen] = useState(false)

  const headerRef = React.useRef<HTMLElement | null>(null)

  const [registerOpen, setRegisterOpen] = useState(false)
  const [aiOpen, setAiOpen] = useState(false)

  const [me, setMe] = useState<AuthMeResponse | null>(null)
  const [authLoading, setAuthLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  const [registerLoading, setRegisterLoading] = useState(false)
  const [registerError, setRegisterError] = useState<string | null>(null)
  const [registerSeed, setRegisterSeed] = useState<string | null>(null)

  const [aiLoading, setAiLoading] = useState(false)
  const [aiSaving, setAiSaving] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)
  const [aiModels, setAiModels] = useState<OpenRouterModel[]>([])
  const [aiModelId, setAiModelId] = useState<string>('')
  const [aiApiKey, setAiApiKey] = useState<string>('')

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [seed, setSeed] = useState('')

  const refreshMe = React.useCallback(async () => {
    const saved = localStorage.getItem('auth_token')
    if (!saved) {
      setAuthToken(null)
      setMe(null)
      return
    }
    setAuthToken(saved)
    try {
      const m = await authMe()
      setMe(m)
    } catch {
      setAuthToken(null)
      localStorage.removeItem('auth_token')
      setMe(null)
    }
  }, [])

  const shellClass = useMemo(() => {
    const classes = ['app-shell']
    if (propsOpen) classes.push('props-open')
    return classes.join(' ')
  }, [propsOpen])

  React.useEffect(() => {
    if (!isNarrow) setPropsOpen(false)
  }, [isNarrow])

  React.useEffect(() => {
    refreshMe()
    const onFocus = () => refreshMe()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [refreshMe])

  React.useEffect(() => {
    const el = headerRef.current
    if (!el) return

    const update = () => {
      const h = Math.ceil(el.getBoundingClientRect().height)
      if (h > 0) document.documentElement.style.setProperty('--header-height', `${h}px`)
    }

    update()

    let ro: ResizeObserver | null = null
    if (typeof (window as any).ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => update())
      ro.observe(el)
    }

    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('resize', update)
      if (ro) ro.disconnect()
    }
  }, [])

  React.useEffect(() => {
    if (!registerOpen) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setRegisterOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [registerOpen])

  React.useEffect(() => {
    if (!aiOpen) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setAiOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [aiOpen])

  async function openAISettings() {
    setAiOpen(true)
    setAiError(null)
    setAiLoading(true)
    try {
      const [models, cfg] = await Promise.all([listOpenRouterModels(), getOpenRouterConfig()])
      setAiModels(models)
      setAiModelId(cfg.model || '')
      setAiApiKey('')
    } catch (e: any) {
      setAiError(e?.message || 'Failed to load AI settings')
    } finally {
      setAiLoading(false)
    }
  }

  return (
    <PropertiesProvider>
    <div className={shellClass}>
      <header className="app-header" ref={headerRef as any}>
        <div className="app-title">doc_gen</div>

        <div className="header-actions">
          <div className="field" aria-label="Авторизация">
            <span className="field-label">Аккаунт</span>
            {me ? (
              <div className="row row-wrap">
                <span className="muted" title={me.id}>
                  {me.email}
                </span>
                <button className="btn" type="button" onClick={openAISettings}>
                  Модель (OpenRouter)
                </button>
                <button
                  className="btn"
                  type="button"
                  onClick={() => {
                    setAuthToken(null)
                    localStorage.removeItem('auth_token')
                    setMe(null)
                  }}
                >
                  Выйти
                </button>
              </div>
            ) : (
              <div className="stack-tight">
                {authError ? <div className="alert">{authError}</div> : null}

                <div className="row row-wrap">
                  <input
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="email"
                    style={{ maxWidth: 220 }}
                  />
                  <input
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="пароль"
                    type="password"
                    style={{ maxWidth: 160 }}
                  />
                  <button
                    className="btn"
                    type="button"
                    disabled={authLoading}
                    onClick={async () => {
                      setAuthLoading(true)
                      setAuthError(null)
                      try {
                        const resp = await authLoginEmail({ email, password })
                        localStorage.setItem('auth_token', resp.access_token)
                        setAuthToken(resp.access_token)
                        await refreshMe()
                      } catch (e: any) {
                        setAuthError(e?.message || 'Login failed')
                      } finally {
                        setAuthLoading(false)
                      }
                    }}
                  >
                    Войти
                  </button>
                  <button
                    className="btn"
                    type="button"
                    onClick={async () => {
                      setRegisterError(null)
                      setRegisterSeed(null)
                      setRegisterOpen(true)
                    }}
                  >
                    Регистрация
                  </button>
                </div>

                <div className="row row-wrap">
                  <input
                    value={seed}
                    onChange={(e) => setSeed(e.target.value)}
                    placeholder="seed фраза (вставьте сюда)"
                    style={{ maxWidth: 420 }}
                  />
                  <button
                    className="btn"
                    type="button"
                    disabled={authLoading}
                    onClick={async () => {
                      setAuthLoading(true)
                      setAuthError(null)
                      try {
                        const resp = await authLoginSeed({ seed_phrase: seed })
                        localStorage.setItem('auth_token', resp.access_token)
                        setAuthToken(resp.access_token)
                        await refreshMe()
                      } catch (e: any) {
                        setAuthError(e?.message || 'Seed login failed')
                      } finally {
                        setAuthLoading(false)
                      }
                    }}
                  >
                    Войти по seed
                  </button>
                </div>
              </div>
            )}
          </div>

          <label className="field">
            <span className="field-label">Тема</span>
            <select value={mode} onChange={(e) => setMode(e.target.value as any)}>
              <option value="system">Системная</option>
              <option value="light">Светлая</option>
              <option value="dark">Тёмная</option>
            </select>
          </label>

          <button
            className="btn only-narrow"
            type="button"
            onClick={() => setPropsOpen((v) => !v)}
            aria-expanded={propsOpen}
            aria-controls="properties"
          >
            Сущности
          </button>
        </div>
      </header>

      <div className="app-main">
        <main className="content" aria-label="Основной контент">
          <DocumentsScreen isAuthed={Boolean(me)} />
        </main>

        <aside id="properties" className="properties" aria-label="Редактор сущностей">
          <div className="properties-inner">
            <div className="properties-title">Редактор сущностей</div>
            <PropertiesOutlet />
          </div>
        </aside>

        {isNarrow && propsOpen ? (
          <button className="backdrop" type="button" onClick={() => setPropsOpen(false)} aria-label="Закрыть" />
        ) : null}

        {registerOpen ? (
          <div
            className="modal-backdrop"
            role="dialog"
            aria-modal="true"
            aria-label="Регистрация"
            onMouseDown={() => setRegisterOpen(false)}
          >
            <div className="modal-card" onMouseDown={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <div className="modal-title">Регистрация</div>
                <button className="btn" type="button" onClick={() => setRegisterOpen(false)} aria-label="Закрыть">
                  ✕
                </button>
              </div>

              <div className="stack">
                {registerError ? <div className="alert">{registerError}</div> : null}

                <div className="form-grid">
                  <label className="field">
                    <span className="field-label">Email</span>
                    <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" />
                  </label>
                  <label className="field">
                    <span className="field-label">Пароль</span>
                    <input
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="пароль"
                      type="password"
                    />
                  </label>
                </div>

                <div className="row">
                  <button
                    className="btn"
                    type="button"
                    disabled={registerLoading}
                    onClick={async () => {
                      setRegisterLoading(true)
                      setRegisterError(null)
                      try {
                        const resp = await authRegister({ email, password })
                        localStorage.setItem('auth_token', resp.access_token)
                        setAuthToken(resp.access_token)
                        setRegisterSeed(resp.seed_phrase)
                        await refreshMe()
                      } catch (e: any) {
                        setRegisterError(e?.message || 'Register failed')
                      } finally {
                        setRegisterLoading(false)
                      }
                    }}
                  >
                    Создать аккаунт
                  </button>

                  <button className="btn" type="button" onClick={() => setRegisterOpen(false)}>
                    Закрыть
                  </button>
                </div>

                {registerSeed ? (
                  <div className="card" aria-label="Seed фраза">
                    <div className="muted" style={{ marginBottom: 8 }}>
                      Сохраните seed фразу — она нужна для входа
                    </div>
                    <div className="mono">{registerSeed}</div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}

        {aiOpen ? (
          <div
            className="modal-backdrop"
            role="dialog"
            aria-modal="true"
            aria-label="Настройки модели"
            onMouseDown={() => setAiOpen(false)}
          >
            <div className="modal-card" onMouseDown={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <div className="modal-title">Модель (OpenRouter)</div>
                <button className="btn" type="button" onClick={() => setAiOpen(false)} aria-label="Закрыть">
                  ✕
                </button>
              </div>

              <div className="stack">
                {aiError ? <div className="alert">{aiError}</div> : null}
                {aiLoading ? <div className="muted">Загрузка…</div> : null}

                {!aiLoading ? (
                  <>
                    <label className="field">
                      <span className="field-label">API Key (OpenRouter)</span>
                      <input
                        value={aiApiKey}
                        onChange={(e) => setAiApiKey(e.target.value)}
                        placeholder="sk-or-..."
                        type="password"
                      />
                    </label>

                    <label className="field">
                      <span className="field-label">Модель</span>
                      <select value={aiModelId} onChange={(e) => setAiModelId(e.target.value)}>
                        <option value="">— выберите —</option>
                        {aiModels.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.name ? `${m.name} (${m.id})` : m.id}
                          </option>
                        ))}
                      </select>
                    </label>

                    <div className="row">
                      <button
                        className="btn"
                        type="button"
                        disabled={aiSaving}
                        onClick={async () => {
                          setAiSaving(true)
                          setAiError(null)
                          try {
                            await setOpenRouterConfig({ api_key: aiApiKey || null, model: aiModelId || null })
                            setAiOpen(false)
                          } catch (e: any) {
                            setAiError(e?.message || 'Failed to save AI settings')
                          } finally {
                            setAiSaving(false)
                          }
                        }}
                      >
                        {aiSaving ? 'Сохраняю…' : 'Сохранить'}
                      </button>
                      <button className="btn" type="button" onClick={() => setAiOpen(false)}>
                        Закрыть
                      </button>
                    </div>
                  </>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
    </PropertiesProvider>
  )
}
