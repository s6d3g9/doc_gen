import React from 'react'

type PropertiesSlotContextValue = {
  content: React.ReactNode
  setContent: (node: React.ReactNode) => void
}

const PropertiesSlotContext = React.createContext<PropertiesSlotContextValue | null>(null)

export function PropertiesProvider({ children }: { children: React.ReactNode }) {
  const [content, setContent] = React.useState<React.ReactNode>(null)
  const value = React.useMemo(() => ({ content, setContent }), [content])
  return <PropertiesSlotContext.Provider value={value}>{children}</PropertiesSlotContext.Provider>
}

export function usePropertiesSlot() {
  const ctx = React.useContext(PropertiesSlotContext)
  if (!ctx) throw new Error('usePropertiesSlot must be used within PropertiesProvider')
  return ctx
}

export function PropertiesOutlet() {
  const { content } = usePropertiesSlot()
  return <>{content}</>
}
