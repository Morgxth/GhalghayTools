import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import s from './SuggestionPopup.module.css'

const popupVariants = {
  initial: { opacity: 0, scale: 0.93, y: -6 },
  animate: { opacity: 1, scale: 1,    y: 0,  transition: { type: 'spring', stiffness: 420, damping: 28 } },
  exit:    { opacity: 0, scale: 0.93, y: -6,  transition: { duration: 0.12 } },
}

// На мобильном — bottom sheet снизу
const sheetVariants = {
  initial: { y: '100%', opacity: 0 },
  animate: { y: 0, opacity: 1, transition: { type: 'spring', stiffness: 360, damping: 34 } },
  exit:    { y: '100%', opacity: 0, transition: { duration: 0.18 } },
}

export default function SuggestionPopup({ popup, onSelect, onClose }) {
  const ref = useRef(null)
  const isMobile = window.innerWidth <= 640

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', handler)
    document.addEventListener('touchstart', handler)
    return () => {
      document.removeEventListener('mousedown', handler)
      document.removeEventListener('touchstart', handler)
    }
  }, [onClose])

  const variants = isMobile ? sheetVariants : popupVariants
  const posStyle = isMobile ? {} : { left: popup.x, top: popup.y }

  if (popup.type === 'warning') {
    const [w1, w2] = popup.bigram.split(' ')
    return (
      <motion.div
        ref={ref}
        className={s.popup}
        style={posStyle}
        variants={variants}
        initial="initial"
        animate="animate"
        exit="exit"
      >
        <div className={s.headerWarn}>
          <span className={s.wordWarn}>⚠ Необычное сочетание</span>
          <span className={s.label}>не встречалось в корпусе</span>
        </div>
        <div className={s.warnBody}>
          <span className={s.bigramWord}>{w1}</span>
          <span className={s.bigramArrow}>→</span>
          <span className={s.bigramWord}>{w2}</span>
        </div>
        <p className={s.warnHint}>
          Эти слова часты по отдельности, но никогда не стоят рядом в текстах корпуса
        </p>
      </motion.div>
    )
  }

  return (
    <motion.div
      ref={ref}
      className={s.popup}
      style={posStyle}
      variants={variants}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      <div className={s.header}>
        <span className={s.word}>«{popup.word}»</span>
        <span className={s.label}>не найдено в словаре</span>
      </div>
      {popup.suggestions.length > 0 ? (
        <ul className={s.list}>
          {popup.suggestions.map((sugg, i) => (
            <motion.li
              key={sugg.word}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04, duration: 0.15 }}
            >
              <button className={s.item} onClick={() => onSelect(sugg.word)}>
                <span className={s.suggWord}>{sugg.word}</span>
                {sugg.translation && (
                  <span className={s.translation}>{sugg.translation}</span>
                )}
              </button>
            </motion.li>
          ))}
        </ul>
      ) : (
        <p className={s.empty}>Подсказок нет</p>
      )}
    </motion.div>
  )
}
