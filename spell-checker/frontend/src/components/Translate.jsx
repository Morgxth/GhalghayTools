import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { translateText } from '../api'
import s from './Translate.module.css'

const LANGS = {
  inh: { code: 'inh_Cyrl', label: 'Ингушский' },
  rus: { code: 'rus_Cyrl', label: 'Русский'   },
}

export default function Translate() {
  const [srcLang, setSrcLang] = useState('inh')
  const [srcText, setSrcText] = useState('')
  const [tgtText, setTgtText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  const tgtLang = srcLang === 'inh' ? 'rus' : 'inh'

  function swap() {
    setSrcText(tgtText)
    setTgtText(srcText)
    setSrcLang(tgtLang)
    setError(null)
  }

  async function handleTranslate() {
    if (!srcText.trim() || loading) return
    setLoading(true)
    setError(null)
    setTgtText('')
    try {
      const res = await translateText(srcText, LANGS[srcLang].code, LANGS[tgtLang].code)
      setTgtText(res.translation)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleTranslate()
  }

  const charLen = srcText.length

  return (
    <div className={s.root}>
      <div className={s.langBar}>
        <span className={s.langLabel}>{LANGS[srcLang].label}</span>
        <button className={s.swapBtn} onClick={swap} title="Поменять языки">⇄</button>
        <span className={s.langLabel}>{LANGS[tgtLang].label}</span>
      </div>

      <div className={s.grid}>
        <div className={s.pane}>
          <textarea
            className={s.textarea}
            value={srcText}
            onChange={e => { setSrcText(e.target.value); setTgtText(''); setError(null) }}
            onKeyDown={handleKeyDown}
            placeholder="Введите текст…"
            maxLength={2000}
            rows={7}
          />
          <div className={`${s.charCount} ${charLen > 1800 ? s.charWarn : ''}`}>
            {charLen} / 2000
          </div>
        </div>

        <div className={s.pane}>
          <textarea
            className={`${s.textarea} ${s.textareaResult}`}
            value={tgtText}
            readOnly
            placeholder="Перевод…"
            rows={7}
          />
          <AnimatePresence>
            {error && (
              <motion.div
                className={s.error}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      <div className={s.actions}>
        <button
          className={s.translateBtn}
          onClick={handleTranslate}
          disabled={!srcText.trim() || loading}
        >
          {loading ? (
            <span className={s.dots}>
              {[0,1,2].map(i => <span key={i} className={s.dot} style={{ animationDelay: `${i * 0.18}s` }} />)}
            </span>
          ) : 'Перевести'}
        </button>
        <span className={s.hint}>Ctrl+Enter</span>
      </div>

      <p className={s.footer}>
        Модель:&nbsp;
        <a href="https://huggingface.co/Targimec/nllb-ingush" target="_blank" rel="noreferrer">
          Targimec/nllb-ingush
        </a>
        &nbsp;· NLLB-200
      </p>
    </div>
  )
}
