import axios from 'axios'

const baseUrl = `${import.meta.env.VITE_API_BASE || '/api/v1'}/universe`

const api = axios.create({ baseURL: baseUrl, timeout: 120000 })

function parseSseChunk(buffer, onEvent) {
  const parts = buffer.split('\n\n')
  const rest = parts.pop() || ''
  for (const block of parts) {
    const line = block.split('\n').find((l) => l.startsWith('data: '))
    if (line) {
      try {
        onEvent(JSON.parse(line.slice(6)))
      } catch {
        /* ignore */
      }
    }
  }
  return rest
}

export default {
  stats() {
    return api.get('/stats').then((r) => r.data)
  },
  syncStatus() {
    return api.get('/sync/status').then((r) => r.data)
  },
  sync() {
    return api.post('/sync').then((r) => r.data)
  },
  /** 全量同步：列表 + 上市至今日 K（断点续传） */
  async syncStream(onEvent, options = {}) {
    const syncMode = options.syncMode === 'full' ? 'full' : 'incremental'
    let finalResult = null
    let lastProgress = 0
    let buffer = ''
    try {
      const response = await fetch(`${baseUrl}/sync/stream`, {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ sync_mode: syncMode })
      })
      if (!response.ok) {
        const text = await response.text()
        throw new Error(text || `HTTP ${response.status}`)
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        buffer = parseSseChunk(buffer, (ev) => {
          onEvent(ev)
          if (ev.event === 'error') {
            const err = new Error(ev.error || ev.message || '同步失败')
            err.syncEvent = ev
            throw err
          }
          if (ev.event === 'complete') finalResult = ev
          if (ev.event === 'klines_scanning') lastProgress = ev.current
        })
      }
      if (buffer.trim()) {
        parseSseChunk(`${buffer}\n\n`, (ev) => {
          if (ev.event === 'error') {
            const err = new Error(ev.error || ev.message || '同步失败')
            err.syncEvent = ev
            throw err
          }
          onEvent(ev)
          if (ev.event === 'complete') finalResult = ev
        })
      }
    } catch (e) {
      throw e
    }
    return {
      final: finalResult,
      interrupted: !finalResult || finalResult.paused === true,
      lastProgress,
      error: null
    }
  },
  getCustom() {
    return api.get('/custom').then((r) => r.data)
  },
  setCustom(symbols) {
    return api.put('/custom', { symbols }).then((r) => r.data)
  }
}
