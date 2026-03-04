const B = import.meta.env.BASE_URL + 'api';

export async function checkText(text) {
  const res = await fetch(`${B}/spell-check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) throw new Error('Ошибка API')
  return res.json()
}

export async function getStatus() {
  const res = await fetch(`${B}/spell-check/status`)
  if (!res.ok) throw new Error('Ошибка API')
  return res.json()
}

export async function getDictionary(q = '', page = 0, size = 50, onlyWithTranslation = false) {
  const params = new URLSearchParams({ q, page, size, onlyWithTranslation })
  const res = await fetch(`${B}/spell-check/dictionary?${params}`)
  if (!res.ok) throw new Error('Ошибка API')
  return res.json()
}

export async function getWordCard(word) {
  const res = await fetch(`${B}/spell-check/dictionary/${encodeURIComponent(word)}`)
  if (!res.ok) throw new Error('Ошибка API')
  return res.json()
}

export async function submitSuggestion(word, translation, comment = '') {
  const res = await fetch(`${B}/spell-check/suggestions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ word, translation, comment }),
  })
  if (!res.ok) throw new Error('Ошибка API')
  return res.json()
}
