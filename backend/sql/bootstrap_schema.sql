-- Bootstrap business tables used by the Django/DRF backend.
-- Safe to run multiple times.

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS locations (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    province VARCHAR(255) NOT NULL,
    geometry JSONB
);

CREATE TABLE IF NOT EXISTS user_activity_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    activity_type VARCHAR(100) NOT NULL,
    page VARCHAR(100) NOT NULL,
    details JSONB DEFAULT '{}'::jsonb,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rainfall_data (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT NOT NULL REFERENCES locations(id),
    date DATE NOT NULL,
    rainfall_mm DOUBLE PRECISION,
    source VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS temperature_data (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT NOT NULL REFERENCES locations(id),
    date DATE NOT NULL,
    temp_min DOUBLE PRECISION,
    temp_max DOUBLE PRECISION,
    temp_mean DOUBLE PRECISION,
    source VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS soil_moisture_data (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT NOT NULL REFERENCES locations(id),
    date DATE NOT NULL,
    sm_surface DOUBLE PRECISION,
    sm_rootzone DOUBLE PRECISION,
    sm_profile DOUBLE PRECISION,
    source VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS ndvi_data (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT NOT NULL REFERENCES locations(id),
    date DATE NOT NULL,
    ndvi_mean DOUBLE PRECISION,
    ndvi_min DOUBLE PRECISION,
    ndvi_max DOUBLE PRECISION,
    ndvi_stddev DOUBLE PRECISION,
    vegetation_area_pct DOUBLE PRECISION,
    source VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS tvdi_data (
    id BIGSERIAL PRIMARY KEY,
    location_id BIGINT NOT NULL REFERENCES locations(id),
    date DATE NOT NULL,
    tvdi_mean DOUBLE PRECISION,
    tvdi_min DOUBLE PRECISION,
    tvdi_max DOUBLE PRECISION,
    lst_mean DOUBLE PRECISION,
    drought_area_pct DOUBLE PRECISION,
    drought_class VARCHAR(50),
    source VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_user_activity_logs_user_id_created_at
    ON user_activity_logs(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_locations_name ON locations(name);

CREATE UNIQUE INDEX IF NOT EXISTS uq_rainfall_location_date
    ON rainfall_data(location_id, date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_temperature_location_date
    ON temperature_data(location_id, date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_soil_moisture_location_date
    ON soil_moisture_data(location_id, date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ndvi_location_date
    ON ndvi_data(location_id, date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_tvdi_location_date
    ON tvdi_data(location_id, date);

-- Seed default location so dropdown is never empty on first run.
INSERT INTO locations (name, province, geometry)
SELECT 'Quang Tri', 'Quang Tri', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM locations WHERE LOWER(name) = 'quang tri'
);
