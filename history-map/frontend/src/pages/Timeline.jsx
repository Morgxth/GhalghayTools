import { useState, useEffect } from 'react';
import { api } from '../api';

const CATEGORIES = [
  { value: '',               label: 'Все категории' },
  { value: 'administrative', label: 'Административные' },
  { value: 'deportation',    label: 'Депортации' },
  { value: 'military',       label: 'Военные' },
  { value: 'documentary',    label: 'Документальные' },
  { value: 'modern',         label: 'Современные' },
];

const LABEL = {
  administrative: 'Административное',
  deportation:    'Депортация',
  military:       'Военное',
  documentary:    'Документальное',
  modern:         'Современное',
  cultural:       'Культурное',
};

const ERAS = [
  { label: 'Имперский период',  from: 0,    to: 1917 },
  { label: 'Советский период',  from: 1917, to: 1991 },
  { label: 'Новейшее время',    from: 1991, to: 9999 },
];

function groupByEra(events) {
  const groups = ERAS.map(era => ({
    ...era,
    items: events.filter(e => e.year >= era.from && e.year < era.to),
  }));
  return groups.filter(g => g.items.length > 0);
}

export default function Timeline() {
  const [events, setEvents]     = useState([]);
  const [loading, setLoading]   = useState(true);
  const [expanded, setExpanded] = useState(new Set());
  const [modal, setModal]       = useState(null);
  const [filters, setFilters]   = useState({ year_from: '', year_to: '', category: '' });

  useEffect(() => {
    setLoading(true);
    api.getEvents(Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')))
      .then(data => setEvents([...data].sort((a, b) => a.year - b.year)))
      .finally(() => setLoading(false));
  }, [filters]);

  const set = (k, v) => setFilters(f => ({ ...f, [k]: v }));

  const toggleExpand = (id) => setExpanded(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const groups = groupByEra(events);

  return (
    <>
      <div className="page-header">
        <h1>Хронология</h1>
        <p>Ключевые события истории Ингушетии — {events.length} записей</p>
      </div>

      <div className="filters">
        <input
          type="number" placeholder="Год от" value={filters.year_from}
          onChange={e => set('year_from', e.target.value)}
          style={{ width: 100 }}
        />
        <input
          type="number" placeholder="Год до" value={filters.year_to}
          onChange={e => set('year_to', e.target.value)}
          style={{ width: 100 }}
        />
        <select value={filters.category} onChange={e => set('category', e.target.value)} style={{ width: 200 }}>
          {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        {(filters.year_from || filters.year_to || filters.category) && (
          <button onClick={() => setFilters({ year_from: '', year_to: '', category: '' })}>
            Сбросить
          </button>
        )}
      </div>

      {loading && <div className="loading">Загрузка</div>}

      {!loading && events.length === 0 && (
        <div className="empty">Событий не найдено</div>
      )}

      {!loading && groups.map(group => (
        <div key={group.label} style={{ marginBottom: 36 }}>
          {/* Заголовок эпохи */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            marginBottom: 20, marginLeft: -4,
          }}>
            <div style={{
              fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
              letterSpacing: 1.5, color: 'var(--text2)',
              padding: '4px 12px',
              background: 'var(--bg3)',
              border: '1px solid var(--border)',
              borderRadius: 20,
              whiteSpace: 'nowrap',
            }}>
              {group.label}
            </div>
            <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            <span style={{ fontSize: 12, color: 'var(--text2)', whiteSpace: 'nowrap' }}>
              {group.items.length} событий
            </span>
          </div>

          <div className="timeline">
            {group.items.map(e => {
              const isExpanded = expanded.has(e.id);
              const isLong = e.descriptionRu?.length > 300;

              return (
                <div key={e.id} className="tl-item">
                  <div className="tl-year">{e.year} г.</div>
                  <span className={`badge badge-${e.category}`}>
                    {LABEL[e.category] ?? e.category}
                  </span>

                  <div
                    className="tl-title"
                    onClick={() => setModal(e)}
                    style={{ cursor: 'pointer' }}
                  >
                    {e.titleRu}
                  </div>

                  {/* Описание — разворачивается */}
                  <div className="tl-desc" style={{
                    maxHeight: isExpanded ? 'none' : undefined,
                  }}>
                    {isExpanded || !isLong
                      ? e.descriptionRu
                      : e.descriptionRu?.slice(0, 300) + '…'
                    }
                  </div>

                  {/* Кнопка развернуть/свернуть */}
                  {isLong && (
                    <button
                      onClick={() => toggleExpand(e.id)}
                      style={{
                        marginTop: 6, fontSize: 12,
                        background: 'none', color: 'var(--accent)',
                        padding: '2px 0', textDecoration: 'underline',
                      }}
                    >
                      {isExpanded ? 'Свернуть ↑' : 'Читать полностью ↓'}
                    </button>
                  )}

                  {/* Источник */}
                  {e.sourceRef && (
                    <div className="tl-source">Источник: {e.sourceRef}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* Модалка с полным текстом */}
      {modal && (
        <div className="modal-overlay" onClick={() => setModal(null)}>
          <div className="modal" onClick={ev => ev.stopPropagation()}>
            <button className="modal-close" onClick={() => setModal(null)}>×</button>
            <span className={`badge badge-${modal.category}`}>
              {LABEL[modal.category] ?? modal.category}
            </span>
            <h2>{modal.titleRu}</h2>
            <div className="meta">{modal.year} г.</div>
            <p style={{ whiteSpace: 'pre-line' }}>{modal.descriptionRu}</p>
            {modal.sourceRef && (
              <div className="source-ref">Источник: {modal.sourceRef}</div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
