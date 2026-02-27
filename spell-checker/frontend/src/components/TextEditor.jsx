import { useRef, useState, useCallback } from 'react'
import { AnimatePresence } from 'framer-motion'
import SuggestionPopup from './SuggestionPopup'
import s from './TextEditor.module.css'

/**
 * Редактор с подсветкой ошибок.
 * Техника overlay: прозрачный textarea поверх div с подсвеченным текстом.
 */
export default function TextEditor({ corrections, contextWarnings, onTextChange }) {
  const [text, setText] = useState('')
  const [popup, setPopup] = useState(null) // { word, position, suggestions, x, y }
  const textareaRef = useRef(null)

  const handleChange = useCallback((e) => {
    const val = e.target.value
    setText(val)
    onTextChange(val)
    setPopup(null)
  }, [onTextChange])

  // Строим HTML с подсветкой на основе corrections
  const buildHighlighted = () => {
    if (!text) return '<span style="color:#475569">Введи текст на ингушском языке...</span>'

    const errorPositions = new Set(corrections.map(c => c.position))
    const warnBigrams = new Set(contextWarnings.map(w => w.bigram))

    const words = text.split(/(\s+)/)
    let wordIdx = 0
    return words.map((chunk) => {
      if (/^\s+$/.test(chunk)) return chunk.replace(/\n/g, '<br>')

      const isError = errorPositions.has(wordIdx)
      const correction = corrections.find(c => c.position === wordIdx)

      // Подсвечиваем оба слова биграммы (позиция w2 = w.position, w1 = w.position-1)
      const isWarning = contextWarnings.some(w =>
        w.position - 1 === wordIdx || w.position === wordIdx
      )

      wordIdx++

      if (isError) {
        const dataAttr = correction
          ? `data-word="${correction.word}" data-position="${correction.position}" data-suggestions='${JSON.stringify(correction.suggestions)}'`
          : ''
        return `<mark class="error" ${dataAttr}>${chunk}</mark>`
      }
      if (isWarning) {
        return `<mark class="warning">${chunk}</mark>`
      }
      return chunk
    }).join('')
  }

  const handleOverlayClick = (e) => {
    const mark = e.target.closest('mark.error')
    if (!mark) { setPopup(null); return }

    const word = mark.dataset.word
    let suggestions = []
    try { suggestions = JSON.parse(mark.dataset.suggestions || '[]') } catch {}

    const rect = mark.getBoundingClientRect()
    const containerRect = e.currentTarget.getBoundingClientRect()

    // Определяем позицию слова в тексте
    const position = parseInt(mark.dataset.position ?? '-1', 10)

    setPopup({
      type: 'correction',
      word,
      position,
      suggestions,
      x: rect.left - containerRect.left,
      y: rect.bottom - containerRect.top + 4,
    })
  }

  const handleTextareaClick = (e) => {
    e.stopPropagation() // не даём событию всплыть до handleOverlayClick
    const cursorPos = e.target.selectionStart
    const chunks = text.split(/(\s+)/)
    let charIdx = 0
    let wordIdx = 0
    let clickedWordIdx = -1

    for (const chunk of chunks) {
      if (/^\s+$/.test(chunk)) {
        charIdx += chunk.length
        continue
      }
      if (cursorPos >= charIdx && cursorPos <= charIdx + chunk.length) {
        clickedWordIdx = wordIdx
        break
      }
      charIdx += chunk.length
      wordIdx++
    }

    if (clickedWordIdx === -1) { setPopup(null); return }

    const correction = corrections.find(c => c.position === clickedWordIdx)
    if (correction) {
      setPopup({
        type: 'correction',
        word: correction.word,
        position: correction.position,
        suggestions: correction.suggestions,
        x: e.clientX,
        y: e.clientY + 4,
      })
      return
    }

    const warning = contextWarnings.find(w =>
      w.position - 1 === clickedWordIdx || w.position === clickedWordIdx
    )
    if (warning) {
      setPopup({
        type: 'warning',
        bigram: warning.bigram,
        score: warning.score,
        x: e.clientX,
        y: e.clientY + 4,
      })
      return
    }

    setPopup(null)
  }

  const applySuggestion = (suggestion) => {
    if (!popup || popup.type !== 'correction') return
    // Заменяем слово по его индексу (позиции), а не regex — чтобы работала кириллица
    const parts = text.split(/(\s+)/)
    let wordIdx = 0
    const newParts = parts.map((chunk) => {
      if (/^\s+$/.test(chunk)) return chunk
      const result = wordIdx === popup.position ? suggestion : chunk
      wordIdx++
      return result
    })
    const newText = newParts.join('')
    setText(newText)
    onTextChange(newText)
    setPopup(null)
  }

  return (
    <div className={s.wrapper}>
      <div className={s.container} onClick={handleOverlayClick}>
        {/* Слой с подсветкой */}
        <div
          className={s.highlight}
          dangerouslySetInnerHTML={{ __html: buildHighlighted() }}
        />
        {/* Прозрачный textarea сверху */}
        <textarea
          ref={textareaRef}
          className={s.textarea}
          value={text}
          onChange={handleChange}
          onClick={handleTextareaClick}
          spellCheck={false}
          placeholder=" "
        />
        <AnimatePresence>
          {popup && (
            <SuggestionPopup
              popup={popup}
              onSelect={applySuggestion}
              onClose={() => setPopup(null)}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
