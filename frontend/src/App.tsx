import React, { useCallback, useMemo, useState } from 'react'
import Spinner from './components/Spinner'
import ResultCard from './components/ResultCard'

const DEFAULT_PLACEHOLDER = 'What did my shopping transactions look like this week?'

export default function App() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [payload, setPayload] = useState<any | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleAsk = useCallback(async () => {
    const q = question.trim()
    if (!q) {
      setError('Please enter a question.')
      return
    }
    setError(null)
    setLoading(true)
    setPayload(null)
    try {
      const resp = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q })
      })
      const data = await resp.json()
      let normalized = data
      if (data && typeof data === 'object' && 'result' in data) {
        normalized = data.result
      }
      setPayload(normalized)
    } catch (e: any) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [question])

  const canAsk = useMemo(() => question.trim().length > 0 && !loading, [question, loading])

  return (
    <div className="page">
      <div className="container">
        <header className="header">
          <h1>Banking Assistant</h1>
          <p className="muted">Ask a question about your banking data.</p>
        </header>

        <section className="input-card">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={DEFAULT_PLACEHOLDER}
            rows={6}
          />
          <div className="actions">
            <button onClick={handleAsk} disabled={!canAsk}>Ask</button>
            <span className="hint">Press ⌘/Ctrl + Enter</span>
          </div>
        </section>

        {error && (
          <div className="error">{error}</div>
        )}

        {payload && (
          <ResultCard payload={payload} />
        )}
      </div>

      {loading && (
        <div className="overlay"><Spinner /></div>
      )}
    </div>
  )
} 