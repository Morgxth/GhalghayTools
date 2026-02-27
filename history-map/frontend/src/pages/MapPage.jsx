import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polygon, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import { api } from '../api';
import { BORDERS } from '../data/historicalBorders';

// Фикс иконок Leaflet + Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

// Цветные SVG-маркеры
const COLORS = {
  administrative: '#7ea8c9',
  deportation:    '#e05252',
  military:       '#d4a017',
  documentary:    '#52b788',
  modern:         '#a0bcd8',
  cultural:       '#c09fd8',
  toponym:        '#c9935a',
};

function makeIcon(color) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36" width="24" height="36">
    <path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24S24 21 24 12C24 5.4 18.6 0 12 0z"
      fill="${color}" stroke="#fff" stroke-width="1.5"/>
    <circle cx="12" cy="12" r="5" fill="#fff" opacity=".9"/>
  </svg>`;
  return L.divIcon({ html: svg, className: '', iconSize: [24, 36], iconAnchor: [12, 36], popupAnchor: [0, -36] });
}

const LABEL = {
  administrative: 'Административное',
  deportation:    'Депортация',
  military:       'Военное',
  documentary:    'Документальное',
  modern:         'Современное',
  cultural:       'Культурное',
  toponym:        'Топоним',
};

const ERAS = [
  { label: 'До 1860',   from: 0,    to: 1859 },
  { label: '1860–1900', from: 1860, to: 1900 },
  { label: '1900–1944', from: 1901, to: 1944 },
  { label: '1944–1991', from: 1945, to: 1991 },
  { label: '1991–2018', from: 1992, to: 2018 },
  { label: 'Все эпохи', from: 0,    to: 9999 },
];

function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 0) {
      map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 10 });
    }
  }, []);
  return null;
}

export default function MapPage() {
  const [events, setEvents]       = useState([]);
  const [toponyms, setToponyms]   = useState([]);
  const [loading, setLoading]     = useState(true);
  const [eraIdx, setEraIdx]       = useState(5);
  const [showEvents, setShowEvents]     = useState(true);
  const [showToponyms, setShowToponyms] = useState(true);
  const [showBorders, setShowBorders]   = useState(true);
  const [categories, setCategories]     = useState(new Set(Object.keys(COLORS)));

  useEffect(() => {
    Promise.all([api.getEvents(), api.getToponyms()])
      .then(([ev, tp]) => { setEvents(ev); setToponyms(tp); })
      .finally(() => setLoading(false));
  }, []);

  const era = ERAS[eraIdx];

  const visibleEvents = events.filter(e =>
    showEvents && e.lat != null && e.lon != null &&
    categories.has(e.category) &&
    e.year >= era.from && e.year <= era.to
  );

  const visibleToponyms = toponyms.filter(t => showToponyms && t.lat != null && t.lon != null);

  const visibleBorders = showBorders
    ? BORDERS.filter(b => b.eraIndexes.includes(eraIdx) || eraIdx === 5)
    : [];

  const allPoints = [
    ...events.filter(e => e.lat).map(e => [e.lat, e.lon]),
    ...toponyms.filter(t => t.lat).map(t => [t.lat, t.lon]),
  ];

  const toggleCat = (cat) => setCategories(prev => {
    const next = new Set(prev);
    next.has(cat) ? next.delete(cat) : next.add(cat);
    return next;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - var(--nav-h))' }}>

      {/* ── Панель управления ── */}
      <div style={{
        background: 'var(--bg2)', borderBottom: '1px solid var(--border)',
        padding: '10px 20px', display: 'flex', flexWrap: 'wrap',
        gap: 16, alignItems: 'center', flexShrink: 0,
      }}>

        {/* Слайдер эпох */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 240 }}>
          <div style={{ fontSize: 12, color: 'var(--text2)' }}>
            Эпоха:&nbsp;<strong style={{ color: 'var(--accent)' }}>{era.label}</strong>
            <span style={{ color: 'var(--text2)', marginLeft: 8 }}>
              · {visibleEvents.length} событий · {visibleBorders.length} границ
            </span>
          </div>
          <input
            type="range" min={0} max={ERAS.length - 1} value={eraIdx}
            onChange={e => setEraIdx(+e.target.value)}
            style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text2)' }}>
            {ERAS.map(e => <span key={e.label}>{e.label.split('–')[0]}</span>)}
          </div>
        </div>

        {/* Слои */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: 'var(--text2)' }}>Слои:</span>
          <LayerBtn active={showBorders}   onClick={() => setShowBorders(v => !v)}   label="Границы"   color="var(--green)" />
          <LayerBtn active={showEvents}    onClick={() => setShowEvents(v => !v)}    label="События"   color="var(--accent2)" />
          <LayerBtn active={showToponyms}  onClick={() => setShowToponyms(v => !v)}  label="Топонимы"  color="var(--accent)" />
        </div>

        {/* Категории событий */}
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: 'var(--text2)' }}>Категории:</span>
          {Object.entries(COLORS).filter(([k]) => k !== 'toponym').map(([cat, color]) => (
            <button key={cat} onClick={() => toggleCat(cat)} style={{
              fontSize: 11, padding: '3px 8px',
              background: categories.has(cat) ? color + '22' : 'var(--bg3)',
              color: categories.has(cat) ? color : 'var(--text2)',
              border: `1px solid ${categories.has(cat) ? color : 'var(--border)'}`,
            }}>
              {LABEL[cat]}
            </button>
          ))}
        </div>
      </div>

      {/* ── Карта ── */}
      {loading ? (
        <div className="loading" style={{ flex: 1 }}>Загрузка карты</div>
      ) : (
        <MapContainer center={[43.1, 44.9]} zoom={8} style={{ flex: 1 }}>
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
            maxZoom={19}
          />

          {allPoints.length > 0 && <FitBounds points={allPoints} />}

          {/* ── Исторические границы ── */}
          {visibleBorders.map(border => (
            <Polygon
              key={border.id}
              positions={border.positions}
              pathOptions={{
                color:       border.color,
                fillColor:   border.color,
                fillOpacity: border.id === 'prigorodny' ? 0.20 : 0.10,
                weight:      border.id === 'prigorodny' ? 2 : 2,
                dashArray:   border.id === 'prigorodny' ? '6 4' : undefined,
                opacity:     0.8,
              }}
            >
              <Tooltip sticky>
                <div style={{ fontFamily: 'sans-serif', maxWidth: 240 }}>
                  <strong style={{ color: border.color }}>{border.label}</strong>
                  <br />
                  <span style={{ fontSize: 12, color: '#555' }}>{border.sublabel}</span>
                </div>
              </Tooltip>
            </Polygon>
          ))}

          {/* ── Маркеры событий ── */}
          {visibleEvents.map(e => (
            <Marker key={`ev-${e.id}`} position={[e.lat, e.lon]} icon={makeIcon(COLORS[e.category] ?? '#888')}>
              <Popup maxWidth={320}>
                <div style={{ fontFamily: 'sans-serif' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: COLORS[e.category], marginBottom: 4 }}>
                    {LABEL[e.category]} · {e.year} г.
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 6 }}>{e.titleRu}</div>
                  <div style={{ fontSize: 12, lineHeight: 1.55, color: '#333' }}>
                    {e.descriptionRu?.slice(0, 260)}{e.descriptionRu?.length > 260 ? '…' : ''}
                  </div>
                  {e.sourceRef && (
                    <div style={{ marginTop: 8, fontSize: 11, color: '#888', fontStyle: 'italic' }}>
                      {e.sourceRef}
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          ))}

          {/* ── Маркеры топонимов ── */}
          {visibleToponyms.map(t => (
            <Marker key={`tp-${t.id}`} position={[t.lat, t.lon]} icon={makeIcon(COLORS.toponym)}>
              <Popup maxWidth={300}>
                <div style={{ fontFamily: 'sans-serif' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: COLORS.toponym, marginBottom: 4 }}>
                    Топоним
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4 }}>{t.nameRu}</div>
                  {t.nameIng && <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>{t.nameIng}</div>}
                  <div style={{ fontSize: 12, lineHeight: 1.55, color: '#333' }}>
                    {t.etymologyRu?.slice(0, 220)}{t.etymologyRu?.length > 220 ? '…' : ''}
                  </div>
                  {t.modernName && <div style={{ marginTop: 6, fontSize: 11, color: '#888' }}>Совр.: {t.modernName}</div>}
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      )}
    </div>
  );
}

function LayerBtn({ active, onClick, label, color }) {
  return (
    <button onClick={onClick} style={{
      fontSize: 12, padding: '4px 10px',
      background: active ? color + '22' : 'var(--bg3)',
      color: active ? color : 'var(--text2)',
      border: `1px solid ${active ? color : 'var(--border)'}`,
    }}>
      {active ? '● ' : '○ '}{label}
    </button>
  );
}
