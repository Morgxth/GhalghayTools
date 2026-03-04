// В dev: http://localhost:8080/api  (из .env)
// В prod: /api  (из .env.production — тот же домен, что и бекенд)
const BASE = import.meta.env.VITE_API_BASE ?? (import.meta.env.BASE_URL + 'api');

async function get(path) {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const api = {
  getEvents:    (params = {}) => get('/events' + toQuery(params)),
  getEvent:     (id)          => get(`/events/${id}`),
  getSocieties: ()            => get('/societies'),
  getSociety:   (id)          => get(`/societies/${id}`),
  getDocuments: (params = {}) => get('/documents' + toQuery(params)),
  getDocument:  (id)          => get(`/documents/${id}`),
  getToponyms:  (params = {}) => get('/toponyms' + toQuery(params)),
  getPersons:   (params = {}) => get('/persons' + toQuery(params)),
};

function toQuery(params) {
  const s = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null && v !== '')
  ).toString();
  return s ? '?' + s : '';
}
