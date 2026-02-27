import s from './ContextWarnings.module.css'

export default function ContextWarnings({ warnings }) {
  if (!warnings?.length) return null

  return (
    <div className={s.box}>
      <h3 className={s.title}>⚠ Контекстные предупреждения (N-gram)</h3>
      <p className={s.desc}>Эти сочетания слов не встречались в ингушском корпусе</p>
      <ul className={s.list}>
        {warnings.map((w, i) => (
          <li key={i} className={s.item}>
            <span className={s.bigram}>«{w.bigram}»</span>
            <span className={s.score}>вероятность: {w.score.toExponential(2)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
