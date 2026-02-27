import { useState, useEffect } from 'react';
import { api } from '../api';

export default function Archive() {
  const [docs, setDocs]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [selected, setSelected] = useState(null);
  const [filters, setFilters]   = useState({ year_from: '', year_to: '' });

  useEffect(() => {
    setLoading(true);
    api.getDocuments(Object.fromEntries(Object.entries(filters).filter(([,v]) => v !== '')))
      .then(setDocs)
      .finally(() => setLoading(false));
  }, [filters]);

  const set = (k, v) => setFilters(f => ({ ...f, [k]: v }));

  return (
    <>
      <div className="page-header">
        <h1>Архив документов</h1>
        <p>Первоисточники, рапорты, постановления и архивные материалы</p>
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
      </div>

      {loading && <div className="loading">Загрузка</div>}

      {!loading && docs.length === 0 && (
        <div className="empty" style={{ marginTop: 60 }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>📄</div>
          <div>Архивные документы пока не добавлены.</div>
          <div style={{ marginTop: 8, fontSize: 13 }}>
            Здесь будут рапорты, постановления ВЦИК, материалы переписей и другие первоисточники.
          </div>
        </div>
      )}

      {!loading && docs.length > 0 && (
        <div className="card-grid">
          {docs.map(d => (
            <div key={d.id} className="card" onClick={() => setSelected(d)}>
              <h3>{d.title}</h3>
              <div style={{ fontSize: 12, color: 'var(--accent)', marginBottom: 6 }}>
                {d.year && `${d.year} г.`}{d.author && ` · ${d.author}`}
              </div>
              <p style={{ color: 'var(--text2)', fontSize: 13 }}>
                {d.textRu?.length > 180 ? d.textRu.slice(0, 180) + '…' : d.textRu}
              </p>
              {d.archiveRef && (
                <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 8 }}>
                  {d.archiveRef}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setSelected(null)}>×</button>
            <h2>{selected.title}</h2>
            <div className="meta">
              {selected.year && `${selected.year} г.`}
              {selected.author && ` · ${selected.author}`}
            </div>
            <p style={{ whiteSpace: 'pre-line' }}>{selected.textRu}</p>
            {selected.archiveRef && (
              <div className="source-ref">Архивная ссылка: {selected.archiveRef}</div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
