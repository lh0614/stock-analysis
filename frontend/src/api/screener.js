import { API_BASE_URL, createApiClient } from './http.js'
import { readSseStream } from './sse.js'

const api = createApiClient('/screener', { timeout: 300000 })

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
    const response = await fetch(`${API_BASE_URL}/screener/run/stream`, {
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
    return readSseStream(response, {
      onEvent,
      isFinalEvent: (ev) => ev.event === 'complete'
    })
  }
}
