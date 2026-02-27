import { useState, useEffect } from 'react'
import { getWordCard, submitSuggestion } from '../api'
import s from './WordCard.module.css'

export default function WordCard({ word, onClose }) {
  const [card, setCard]         = useState(null)
  const [loading, setLoading]   = useState(true)
  const [suggesting, setSuggesting] = useState(false)
  const [form, setForm]         = useState({ translation: '', comment: '' })
  const [sent, setSent]         = useState(false)
  const [sending, setSending]   = useState(false)

  useEffect(() => {
    setLoading(true)
    getWordCard(word)
      .then(setCard)
      .finally(() => setLoading(false))
  }, [word])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.translation.trim()) return
    setSending(true)
    try {
      await submitSuggestion(card.word, form.translation, form.comment)
      setSent(true)
    } catch {
      alert('Ошибка при отправке')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className={s.overlay} onClick={onClose}>
      <div className={s.card} onClick={e => e.stopPropagation()}>
        <button className={s.close} onClick={onClose}>✕</button>

        {loading && <div className={s.loading}>загрузка...</div>}

        {card && !loading && (
          <>
            <h2 className={s.word}>{card.word}</h2>

            <div className={s.section}>
              <span className={s.label}>Перевод</span>
              <span className={s.value}>
                {card.translation || <span className={s.empty}>не указан</span>}
              </span>
            </div>

            <div className={s.section}>
              <span className={s.label}>Частота в корпусе</span>
              <span className={s.value}>
                {card.frequency > 0
                  ? `${card.frequency.toLocaleString()} вхождений`
                  : <span className={s.empty}>не встречается</span>}
              </span>
            </div>

            {card.related.length > 0 && (
              <div className={s.section}>
                <span className={s.label}>Похожие слова</span>
                <div className={s.related}>
                  {card.related.map(w => (
                    <button
                      key={w}
                      className={s.relatedWord}
                      onClick={() => { onClose(); setTimeout(() => onClose(w), 0) }}
                    >
                      {w}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className={s.divider} />

            {!suggesting && !sent && (
              <button className={s.suggestBtn} onClick={() => setSuggesting(true)}>
                {card.translation ? 'Предложить исправление' : 'Предложить перевод'}
              </button>
            )}

            {suggesting && !sent && (
              <form className={s.form} onSubmit={handleSubmit}>
                <label className={s.formLabel}>
                  Предлагаемый перевод
                  <input
                    className={s.input}
                    type="text"
                    value={form.translation}
                    onChange={e => setForm(f => ({ ...f, translation: e.target.value }))}
                    placeholder="на русском языке"
                    autoFocus
                  />
                </label>
                <label className={s.formLabel}>
                  Комментарий (необязательно)
                  <input
                    className={s.input}
                    type="text"
                    value={form.comment}
                    onChange={e => setForm(f => ({ ...f, comment: e.target.value }))}
                    placeholder="источник, уточнение..."
                  />
                </label>
                <div className={s.formActions}>
                  <button type="button" className={s.cancelBtn} onClick={() => setSuggesting(false)}>
                    Отмена
                  </button>
                  <button type="submit" className={s.submitBtn} disabled={sending}>
                    {sending ? 'Отправка...' : 'Отправить'}
                  </button>
                </div>
                <p className={s.note}>
                  Предложение попадает в очередь модерации и не меняет словарь сразу.
                </p>
              </form>
            )}

            {sent && (
              <div className={s.success}>
                Спасибо! Предложение отправлено на проверку.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
