import { useState, useEffect, useRef, useCallback } from 'react'
import { getDictionary } from '../api'
import WordCard from './WordCard'
import s from './Dictionary.module.css'

const PAGE_SIZE = 50

export default function Dictionary() {
  const [query, setQuery]               = useState('')
  const [onlyWithTranslation, setOnly]  = useState(false)
  const [words, setWords]               = useState([])
  const [total, setTotal]               = useState(null)
  const [page, setPage]                 = useState(0)
  const [loading, setLoading]           = useState(false)
  const [selectedWord, setSelectedWord] = useState(null)
  const debounceRef = useRef(null)

  const load = useCallback(async (q, p, only) => {
    setLoading(true)
    try {
      const data = await getDictionary(q, p, PAGE_SIZE, only)
      setWords(data.words)
      setTotal(data.total)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setPage(0)
      load(query, 0, onlyWithTranslation)
    }, 300)
    return () => clearTimeout(debounceRef.current)
  }, [query, onlyWithTranslation, load])

  useEffect(() => {
    load(query, page, onlyWithTranslation)
  }, [page]) // eslint-disable-line

  const totalPages = total !== null ? Math.ceil(total / PAGE_SIZE) : 0

  return (
    <div className={s.root}>
      <div className={s.searchRow}>
        <input
          className={s.search}
          type="text"
          placeholder="Поиск по словарю..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          autoFocus
        />
        <label className={s.toggle}>
          <input
            type="checkbox"
            checked={onlyWithTranslation}
            onChange={e => setOnly(e.target.checked)}
          />
          только с переводом
        </label>
        {total !== null && (
          <span className={s.count}>
            {loading ? 'загрузка...' : `${total.toLocaleString()} слов`}
          </span>
        )}
      </div>

      <table className={s.table}>
        <thead>
          <tr>
            <th>Ингушское слово</th>
            <th>Перевод</th>
          </tr>
        </thead>
        <tbody>
          {words.map(({ word, translation }) => (
            <tr key={word} className={s.row} onClick={() => setSelectedWord(word)}>
              <td className={s.word}>{word}</td>
              <td className={s.translation}>{translation || <span className={s.noTr}>—</span>}</td>
            </tr>
          ))}
          {words.length === 0 && !loading && (
            <tr>
              <td colSpan={2} className={s.empty}>Ничего не найдено</td>
            </tr>
          )}
        </tbody>
      </table>

      {totalPages > 1 && (
        <div className={s.pagination}>
          <button
            className={s.pageBtn}
            disabled={page === 0}
            onClick={() => setPage(p => p - 1)}
          >
            ←
          </button>
          <span className={s.pageInfo}>
            {page + 1} / {totalPages}
          </span>
          <button
            className={s.pageBtn}
            disabled={page >= totalPages - 1}
            onClick={() => setPage(p => p + 1)}
          >
            →
          </button>
        </div>
      )}

      {selectedWord && (
        <WordCard
          word={selectedWord}
          onClose={() => setSelectedWord(null)}
        />
      )}
    </div>
  )
}
