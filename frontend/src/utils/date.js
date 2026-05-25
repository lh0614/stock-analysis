/** 本地日历日 YYYY-MM-DD（避免 toISOString 用 UTC 导致东八区早上少一天） */
export function formatLocalDate(date = new Date()) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}
