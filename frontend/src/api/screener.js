import axios from 'axios'

const baseUrl = `${import.meta.env.VITE_API_BASE || '/api/v1'}/screener`

const api = axios.create({ baseURL: baseUrl, timeout: 300000 })

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
  presets() {
    return api.get('/presets').then((r) => r.data)
  },
  runResults(runId, page = 1, pageSize = 20) {
    return api
      .get(`/runs/${runId}/results`, { params: { page, page_size: pageSize } })
      .then((r) => r.data)
  },
  async runStream(presetIds, onEvent, options = {}) {
    const ids = Array.isArray(presetIds) ? presetIds : presetIds ? [presetIds] : []
    const response = await fetch(`${baseUrl}/run/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({
        preset_ids: ids.length ? ids : undefined,
        preset_id: ids.length === 1 ? ids[0] : undefined,
        ...(options.maxScan != null && options.maxScan > 0
          ? { max_scan: options.maxScan }
          : {}),
        include_chinext: options.includeChinext ?? false,
        include_star: options.includeStar ?? false,
        include_bse: options.includeBse ?? false,
        exclude_st: options.excludeSt ?? true,
        use_custom_pool: options.useCustomPool ?? false,
        prefer_local_cache: options.preferLocalCache ?? true
      })
    })
    if (!response.ok) throw new Error(await response.text())
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalResult = null
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      buffer = parseSseChunk(buffer, (ev) => {
        onEvent(ev)
        if (ev.event === 'complete') finalResult = ev.result
      })
    }
    return finalResult
  }
}
