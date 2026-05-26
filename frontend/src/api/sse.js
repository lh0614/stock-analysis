export function parseSseChunk(buffer, onEvent) {
  const parts = buffer.split('\n\n')
  const rest = parts.pop() || ''
  for (const block of parts) {
    const line = block.split('\n').find((l) => l.startsWith('data: '))
    if (line) {
      try {
        onEvent(JSON.parse(line.slice(6)))
      } catch {
        /* ignore malformed */
      }
    }
  }
  return rest
}

/**
 * Read parsed SSE events from a fetch Response body stream.
 * @param {Response} response - ok response with a readable body
 * @param {object} options
 * @param {(ev: object) => void} [options.onEvent]
 * @param {(ev: object) => boolean} [options.isFinalEvent] - when true, ev.result becomes the return value
 * @param {boolean} [options.flushRemainder] - parse any trailing buffer after the stream ends
 * @returns {Promise<*>} last matching final event's result, or null
 */
export async function readSseStream(response, { onEvent = () => {}, isFinalEvent = () => false, flushRemainder = false } = {}) {
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult = null

  const handleEvent = (ev) => {
    onEvent(ev)
    if (isFinalEvent(ev)) {
      finalResult = ev.result
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    buffer = parseSseChunk(buffer, handleEvent)
  }
  if (flushRemainder && buffer) {
    parseSseChunk(buffer + '\n\n', handleEvent)
  }
  return finalResult
}
