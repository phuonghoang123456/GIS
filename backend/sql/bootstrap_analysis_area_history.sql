-- Bootstrap table for storing recent geometry analysis areas by authenticated user.
-- Safe to run multiple times.

CREATE TABLE IF NOT EXISTS analysis_area_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    province_name VARCHAR(255),
    source_type VARCHAR(50) NOT NULL,
    boundary_code VARCHAR(50),
    location_id BIGINT REFERENCES locations(id),
    geometry JSONB NOT NULL,
    centroid_lat DOUBLE PRECISION,
    centroid_lng DOUBLE PRECISION,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_area_history_user_last_used
    ON analysis_area_history(user_id, last_used_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_area_history_location_id
    ON analysis_area_history(location_id);
