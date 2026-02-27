import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { getStatus } from '../api'
import s from './StatsPanel.module.css'

function useCountUp(target, duration = 1100) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    if (!target) return
    const start = Date.now()
    const tick = () => {
      const progress = Math.min((Date.now() - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 4) // ease-out quart
      setValue(Math.round(eased * target))
      if (progress < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }, [target, duration])
  return value
}

export default function StatsPanel() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    getStatus().then(setStats).catch(() => {})
  }, [])

  if (!stats) return null

  const items = [
    { label: 'Слов в словаре', value: stats.dictionarySize, numeric: true },
    { label: 'Биграмм',        value: stats.bigramCount,    numeric: true },
    { label: 'Статус',         value: stats.status === 'ok' ? '✓ онлайн' : '✗ офлайн', isOk: stats.status === 'ok' },
  ]

  return (
    <motion.div
      className={s.panel}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.15, ease: [0.4, 0, 0.2, 1] }}
    >
      {items.map((item, i) => (
        <Stat key={item.label} {...item} delay={i * 0.07} />
      ))}
    </motion.div>
  )
}

function Stat({ label, value, numeric, isOk, delay = 0 }) {
  const counted = useCountUp(numeric ? value : 0)
  const display = numeric
    ? (counted?.toLocaleString('ru') ?? '—')
    : (value ?? '—')

  return (
    <motion.div
      className={s.stat}
      initial={{ opacity: 0, scale: 0.9, y: 6 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 260, damping: 22, delay }}
    >
      <span className={s.label}>{label}</span>
      <span className={`${s.value} ${isOk === true ? s.ok : isOk === false ? s.error : ''}`}>
        {display}
      </span>
    </motion.div>
  )
}
