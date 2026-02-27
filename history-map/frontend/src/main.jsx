import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css'
import './index.css'
import App from './App.jsx'

// Инициализация Telegram Mini App
// window.Telegram.WebApp доступен только внутри Telegram;
// в браузере объект отсутствует — приложение работает в обычном режиме.
const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();    // Сообщаем Telegram: приложение загружено и готово к работе
  tg.expand();   // Разворачиваем на весь экран (без полосы с кнопками Telegram)
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
