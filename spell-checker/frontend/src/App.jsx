import { useState, useCallback, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { checkText } from './api'
import StatsPanel from './components/StatsPanel'
import TextEditor from './components/TextEditor'
import ContextWarnings from './components/ContextWarnings'
import Dictionary from './components/Dictionary'
import Translate from './components/Translate'
import About from './components/About'
import Education from './components/Education'
import Contact from './components/Contact'
import ScrollToTop from './components/ScrollToTop'
import s from './App.module.css'

const DEBOUNCE_MS = 800

const TABS = [
  { id: 'checker',    label: 'Проверка'    },
  { id: 'dictionary', label: 'Словарь'     },
  { id: 'translate',  label: 'Переводчик'  },
  { id: 'about',      label: 'О проекте'   },
  { id: 'education',  label: 'Образование' },
  { id: 'contact',    label: 'Контакты'    },
]

const tabContent = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.22, ease: [0.4, 0, 0.2, 1] } },
  exit:    { opacity: 0, y: -6, transition: { duration: 0.14, ease: [0.4, 0, 1, 1] } },
}

export default function App() {
  const [tab, setTab] = useState('checker')

  const [corrections, setCorrections]         = useState([])
  const [contextWarnings, setContextWarnings] = useState([])
  const [loading, setLoading]                 = useState(false)
  const [errorCount, setErrorCount]           = useState(null)
  const debounceRef = useRef(null)

  const handleTextChange = useCallback((text) => {
    clearTimeout(debounceRef.current)
    if (!text.trim()) {
      setCorrections([])
      setContextWarnings([])
      setErrorCount(null)
      return
    }
    debounceRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const result = await checkText(text)
        setCorrections(result.corrections ?? [])
        setContextWarnings(result.contextWarnings ?? [])
        setErrorCount(result.corrections?.length ?? 0)
      } catch {
        // сервер недоступен
      } finally {
        setLoading(false)
      }
    }, DEBOUNCE_MS)
  }, [])

  return (
    <div>
      <header className={s.header}>
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.34, 1.56, 0.64, 1] }}
        >
          <h1 className={s.title}>ГIалгIай мотт</h1>
          <p className={s.subtitle}>Проверка орфографии ингушского языка</p>
        </motion.div>

        <AnimatePresence>
          {loading && (
            <motion.div
              className={s.loadingWrap}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.15 }}
            >
              {[0, 1, 2].map(i => (
                <motion.span
                  key={i}
                  className={s.dot}
                  animate={{ scale: [0.6, 1.2, 0.6], opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.2, ease: 'easeInOut' }}
                />
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      <StatsPanel />

      <nav className={s.tabs}>
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            className={`${s.tab} ${tab === id ? s.tabActive : ''}`}
            onClick={() => setTab(id)}
          >
            {label}
            {tab === id && (
              <motion.div
                layoutId="tab-indicator"
                className={s.tabIndicator}
                transition={{ type: 'spring', stiffness: 420, damping: 36 }}
              />
            )}
          </button>
        ))}
      </nav>

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={tab}
          variants={tabContent}
          initial="initial"
          animate="animate"
          exit="exit"
        >
          {tab === 'checker' && (
            <>
              <TextEditor
                corrections={corrections}
                contextWarnings={contextWarnings}
                onTextChange={handleTextChange}
              />

              <AnimatePresence>
                {errorCount !== null && (
                  <motion.div
                    className={s.summary}
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 24 }}
                  >
                    {errorCount === 0
                      ? <span className={s.ok}>✓ Ошибок не найдено</span>
                      : <span className={s.err}>✗ Найдено слов не из словаря: {errorCount}</span>
                    }
                    {contextWarnings.length > 0 && (
                      <span className={s.warn}> · {contextWarnings.length} контекстных предупреждений</span>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>

              <ContextWarnings warnings={contextWarnings} />
            </>
          )}

          {tab === 'dictionary' && <Dictionary />}
          {tab === 'translate'  && <Translate />}
          {tab === 'about'      && <About />}
          {tab === 'education'  && <Education />}
          {tab === 'contact'    && <Contact />}
        </motion.div>
      </AnimatePresence>

      <ScrollToTop />
    </div>
  )
}
