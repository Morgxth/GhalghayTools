(() => {
  const APPS = [
    { id: 'spell',      name: 'Орфограф',    icon: 'АА',  url: 'https://spell-checker-production.up.railway.app/spell/',  status: 'live' },
    { id: 'map',        name: 'Карта',        icon: '🗺',   url: 'https://history-map-production-d095.up.railway.app/map/', status: 'live' },
    { id: 'translate',  name: 'Переводчик',   icon: '🔤',  url: 'https://spell-checker-production.up.railway.app/spell/#translate', status: 'live' },
    { id: 'dict',       name: 'Словарь',      icon: '📚',  url: '/dict/',                                                      status: 'soon' },
  ];

  const CSS = `
    :host { position: fixed; top: 14px; right: 16px; z-index: 9999; font-family: system-ui, sans-serif; }

    .trigger {
      width: 36px; height: 36px; border-radius: 8px; border: none; cursor: pointer;
      background: rgba(255,255,255,0.08); backdrop-filter: blur(8px);
      color: rgba(255,255,255,0.75); font-size: 18px; display: grid;
      place-items: center; transition: background 0.15s;
    }
    .trigger:hover { background: rgba(255,255,255,0.15); }
    .trigger.open   { background: rgba(255,255,255,0.18); }

    .panel {
      position: absolute; top: 44px; right: 0;
      width: 228px; padding: 12px;
      background: #1a1d27; border: 1px solid rgba(255,255,255,0.1);
      border-radius: 14px; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
      display: none; grid-template-columns: 1fr 1fr;
      gap: 8px;
      animation: fadeIn 0.15s ease;
    }
    .panel.open { display: grid; }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(-6px) scale(0.97); }
      to   { opacity: 1; transform: translateY(0)   scale(1); }
    }

    .header {
      grid-column: 1 / -1; padding: 2px 4px 8px;
      font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
      color: rgba(255,255,255,0.35); text-transform: uppercase;
    }

    .app {
      display: flex; flex-direction: column; align-items: center; gap: 6px;
      padding: 12px 8px; border-radius: 10px; text-decoration: none;
      transition: background 0.12s;
    }
    .app:hover { background: rgba(255,255,255,0.07); }
    .app.soon  { opacity: 0.4; pointer-events: none; }

    .app-icon {
      width: 44px; height: 44px; border-radius: 10px;
      background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08);
      display: grid; place-items: center;
      font-size: 20px; font-weight: 700; color: rgba(255,255,255,0.9);
    }
    .app-icon.text { font-size: 14px; font-family: system-ui; }

    .app-name {
      font-size: 11px; color: rgba(255,255,255,0.65); text-align: center; line-height: 1.3;
    }
    .app.soon .app-name::after { content: ' •'; color: rgba(255,255,255,0.3); }
  `;

  class AppLauncher extends HTMLElement {
    connectedCallback() {
      const shadow = this.attachShadow({ mode: 'open' });

      const style = document.createElement('style');
      style.textContent = CSS;

      const trigger = document.createElement('button');
      trigger.className = 'trigger';
      trigger.setAttribute('aria-label', 'Приложения');
      trigger.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <circle cx="2.5" cy="2.5" r="1.5"/><circle cx="8" cy="2.5" r="1.5"/><circle cx="13.5" cy="2.5" r="1.5"/>
        <circle cx="2.5" cy="8"   r="1.5"/><circle cx="8" cy="8"   r="1.5"/><circle cx="13.5" cy="8"   r="1.5"/>
        <circle cx="2.5" cy="13.5" r="1.5"/><circle cx="8" cy="13.5" r="1.5"/><circle cx="13.5" cy="13.5" r="1.5"/>
      </svg>`;

      const panel = document.createElement('div');
      panel.className = 'panel';
      panel.innerHTML = `<div class="header">GhalghayTools</div>` +
        APPS.map(a => `
          <a class="app ${a.status}" href="${a.status === 'live' ? a.url : '#'}">
            <div class="app-icon ${/^[А-Яа-яёЁ]/.test(a.icon) ? 'text' : ''}">${a.icon}</div>
            <span class="app-name">${a.name}</span>
          </a>`).join('');

      trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        const open = panel.classList.toggle('open');
        trigger.classList.toggle('open', open);
      });

      document.addEventListener('click', () => {
        panel.classList.remove('open');
        trigger.classList.remove('open');
      });

      shadow.append(style, trigger, panel);
    }
  }

  customElements.define('app-launcher', AppLauncher);
})();
