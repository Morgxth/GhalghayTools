-- ========================================================
-- Инициализация базы данных: IngushHistoryApp
-- ========================================================

CREATE TABLE IF NOT EXISTS events (
    id           BIGSERIAL PRIMARY KEY,
    year         INTEGER,
    title_ru     VARCHAR(500) NOT NULL,
    description_ru TEXT,
    category     VARCHAR(100),
    lat          DOUBLE PRECISION,
    lon          DOUBLE PRECISION,
    source_ref   VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS societies (
    id                 BIGSERIAL PRIMARY KEY,
    name_ru            VARCHAR(200) NOT NULL,
    name_ing           VARCHAR(200),
    description_ru     TEXT,
    territory_geojson  TEXT,
    era_from           INTEGER,
    era_to             INTEGER
);

CREATE TABLE IF NOT EXISTS documents (
    id          BIGSERIAL PRIMARY KEY,
    title       VARCHAR(500) NOT NULL,
    year        INTEGER,
    author      VARCHAR(300),
    text_ru     TEXT,
    archive_ref VARCHAR(500),
    image_url   VARCHAR(1000)
);

CREATE TABLE IF NOT EXISTS toponyms (
    id            BIGSERIAL PRIMARY KEY,
    name_ru       VARCHAR(200) NOT NULL,
    name_ing      VARCHAR(200),
    etymology_ru  TEXT,
    modern_name   VARCHAR(200),
    lat           DOUBLE PRECISION,
    lon           DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS persons (
    id           BIGSERIAL PRIMARY KEY,
    name_ru      VARCHAR(300) NOT NULL,
    years        VARCHAR(50),
    role_ru      VARCHAR(200),
    biography_ru TEXT
);

-- Индексы для поиска
CREATE INDEX IF NOT EXISTS idx_events_year     ON events(year);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
CREATE INDEX IF NOT EXISTS idx_toponyms_name   ON toponyms(name_ru);
CREATE INDEX IF NOT EXISTS idx_persons_role    ON persons(role_ru);
