import { useState, useEffect } from 'react';
import { api } from '../api';

const TABS = ['Общества', 'Топонимы'];

const CAT_LABEL = {
  administrative: 'Административное',
  deportation:    'Депортация',
  military:       'Военное',
  documentary:    'Документальное',
  modern:         'Современное',
  cultural:       'Культурное',
};

/** Ищем в тексте события хотя бы одно из ключевых слов сущности */
function findRelatedEvents(events, keywords) {
  const ks = keywords.map(k => k.toLowerCase()).filter(Boolean);
  return events.filter(e => {
    const hay = ((e.titleRu ?? '') + ' ' + (e.descriptionRu ?? '')).toLowerCase();
    return ks.some(k => k.length > 3 && hay.includes(k));
  });
}

/** Ключевые слова для общества */
function societyKeywords(s) {
  const words = [s.nameRu, s.nameIng];
  // Добавляем короткие формы: «Карабулаки» → «карабулак»
  if (s.nameRu) {
    const stem = s.nameRu.replace(/цы$|ы$|и$|овцы$|евцы$/, '');
    words.push(stem);
  }
  return words;
}

/** Ключевые слова для топонима */
function toponymKeywords(t) {
  return [t.nameRu, t.nameIng, t.modernName];
}

export default function Encyclopedia() {
  const [tab, setTab]             = useState(0);
  const [societies, setSocieties] = useState([]);
  const [toponyms, setToponyms]   = useState([]);
  const [events, setEvents]       = useState([]);
  const [search, setSearch]       = useState('');
  const [loading, setLoading]     = useState(true);
  const [selected, setSelected]   = useState(null);   // { type, data }
  const [relExpanded, setRelExpanded] = useState(false);
  const [eventModal, setEventModal]   = useState(null); // полное событие

  useEffect(() => {
    setLoading(true);
    Promise.all([api.getSocieties(), api.getToponyms(), api.getEvents()])
      .then(([s, t, ev]) => { setSocieties(s); setToponyms(t); setEvents(ev); })
      .finally(() => setLoading(false));
  }, []);

  // При смене выбранной карточки сбрасываем раскрытие
  const openCard = (type, data) => {
    setSelected({ type, data });
    setRelExpanded(false);
  };

  const q = search.toLowerCase();
  const filteredSocieties = societies.filter(s =>
    !q || s.nameRu?.toLowerCase().includes(q) || s.nameIng?.toLowerCase().includes(q)
  );
  const filteredToponyms = toponyms.filter(t =>
    !q || t.nameRu?.toLowerCase().includes(q) || t.nameIng?.toLowerCase().includes(q) || t.modernName?.toLowerCase().includes(q)
  );

  // Связанные события для открытой карточки
  const relatedEvents = selected
    ? findRelatedEvents(
        events,
        selected.type === 'society'
          ? societyKeywords(selected.data)
          : toponymKeywords(selected.data)
      )
    : [];

  const SHOW_LIMIT = 3;
  const visibleRelated = relExpanded ? relatedEvents : relatedEvents.slice(0, SHOW_LIMIT);

  return (
    <>
      <div className="page-header">
        <h1>Энциклопедия</h1>
        <p>Общества, племена и топонимы исторической Ингушетии</p>
      </div>

      <div className="filters">
        <input
          placeholder="Поиск…" value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ maxWidth: 280 }}
        />
        <div style={{ display: 'flex', gap: 6 }}>
          {TABS.map((t, i) => (
            <button key={t} className={tab === i ? 'primary' : ''} onClick={() => setTab(i)}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="loading">Загрузка</div>}

      {/* Карточки обществ */}
      {!loading && tab === 0 && (
        <div className="card-grid">
          {filteredSocieties.map(s => (
            <div key={s.id} className="card" onClick={() => openCard('society', s)}>
              <h3>{s.nameRu}</h3>
              {s.nameIng && <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>{s.nameIng}</div>}
              <p>{s.descriptionRu}</p>
              {(s.eraFrom || s.eraTo) && (
                <div style={{ fontSize: 12, color: 'var(--accent)', marginTop: 8 }}>
                  {s.eraFrom && `c ${s.eraFrom}`}{s.eraTo && ` по ${s.eraTo} г.`}
                </div>
              )}
            </div>
          ))}
          {filteredSocieties.length === 0 && <div className="empty">Ничего не найдено</div>}
        </div>
      )}

      {/* Карточки топонимов */}
      {!loading && tab === 1 && (
        <div className="card-grid">
          {filteredToponyms.map(t => (
            <div key={t.id} className="card" onClick={() => openCard('toponym', t)}>
              <h3>{t.nameRu}</h3>
              {t.nameIng && <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 6 }}>{t.nameIng}</div>}
              <p>{t.etymologyRu}</p>
              {t.modernName && (
                <div style={{ fontSize: 12, color: 'var(--accent2)', marginTop: 8 }}>Совр.: {t.modernName}</div>
              )}
            </div>
          ))}
          {filteredToponyms.length === 0 && <div className="empty">Ничего не найдено</div>}
        </div>
      )}

      {/* Модалка полного события (поверх карточки общества/топонима) */}
      {eventModal && (
        <div
          className="modal-overlay"
          style={{ zIndex: 300 }}
          onClick={() => setEventModal(null)}
        >
          <div className="modal" onClick={ev => ev.stopPropagation()}>
            <button className="modal-close" onClick={() => setEventModal(null)}>×</button>
            <span className={`badge badge-${eventModal.category}`}>
              {CAT_LABEL[eventModal.category] ?? eventModal.category}
            </span>
            <h2 style={{ marginTop: 8 }}>{eventModal.titleRu}</h2>
            <div className="meta">{eventModal.year} г.</div>
            <p style={{ whiteSpace: 'pre-line' }}>{eventModal.descriptionRu}</p>
            {eventModal.sourceRef && (
              <div className="source-ref">Источник: {eventModal.sourceRef}</div>
            )}
          </div>
        </div>
      )}

      {/* Модалка с деталями и связанными событиями */}
      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setSelected(null)}>×</button>

            <h2>{selected.data.nameRu}</h2>
            {selected.data.nameIng && (
              <div className="meta">{selected.data.nameIng}</div>
            )}

            {/* Основной текст */}
            {selected.type === 'society' && (
              <>
                <p>{selected.data.descriptionRu}</p>
                {(selected.data.eraFrom || selected.data.eraTo) && (
                  <div style={{ marginTop: 12, fontSize: 13, color: 'var(--accent)' }}>
                    Период: {selected.data.eraFrom ?? '?'} — {selected.data.eraTo ?? 'настоящее время'}
                  </div>
                )}
              </>
            )}
            {selected.type === 'toponym' && (
              <>
                <p>{selected.data.etymologyRu}</p>
                {selected.data.modernName && (
                  <div style={{ marginTop: 10, fontSize: 13, color: 'var(--accent2)' }}>
                    Современное название: {selected.data.modernName}
                  </div>
                )}
                {selected.data.lat && (
                  <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text2)' }}>
                    Координаты: {selected.data.lat.toFixed(4)}, {selected.data.lon.toFixed(4)}
                  </div>
                )}
              </>
            )}

            {/* Связанные события */}
            <div style={{
              marginTop: 20,
              borderTop: '1px solid var(--border)',
              paddingTop: 16,
            }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: 'var(--text2)' }}>
                Упоминается в событиях
                <span style={{
                  marginLeft: 8,
                  background: 'var(--bg3)',
                  color: 'var(--accent)',
                  fontSize: 11,
                  padding: '2px 7px',
                  borderRadius: 10,
                  fontWeight: 700,
                }}>
                  {relatedEvents.length}
                </span>
              </div>

              {relatedEvents.length === 0 && (
                <div style={{ fontSize: 13, color: 'var(--text2)' }}>
                  Прямых упоминаний в базе событий не найдено.
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {visibleRelated.map(e => (
                  <div
                    key={e.id}
                    onClick={() => setEventModal(e)}
                    style={{
                      background: 'var(--bg3)',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      padding: '10px 12px',
                      cursor: 'pointer',
                      transition: 'border-color .15s',
                    }}
                    onMouseEnter={ev => ev.currentTarget.style.borderColor = 'var(--accent)'}
                    onMouseLeave={ev => ev.currentTarget.style.borderColor = 'var(--border)'}
                  >
                    <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', marginBottom: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)', whiteSpace: 'nowrap' }}>
                        {e.year} г.
                      </span>
                      <span className={`badge badge-${e.category}`} style={{ margin: 0 }}>
                        {CAT_LABEL[e.category] ?? e.category}
                      </span>
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
                      {e.titleRu}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.5 }}>
                      {e.descriptionRu?.slice(0, 200)}{e.descriptionRu?.length > 200 ? '…' : ''}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--accent)', marginTop: 6 }}>
                      Читать полностью →
                    </div>
                  </div>
                ))}
              </div>

              {relatedEvents.length > SHOW_LIMIT && (
                <button
                  onClick={() => setRelExpanded(v => !v)}
                  style={{ marginTop: 10, fontSize: 12, background: 'none', color: 'var(--accent)', textDecoration: 'underline', padding: 0 }}
                >
                  {relExpanded
                    ? 'Свернуть ↑'
                    : `Показать ещё ${relatedEvents.length - SHOW_LIMIT} событий ↓`
                  }
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
