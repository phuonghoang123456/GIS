-- Bootstrap administrative boundary storage for Vietnam level 1/2/3 geometry imports.
-- Safe to run multiple times.

CREATE TABLE IF NOT EXISTS admin_boundaries (
    id BIGSERIAL PRIMARY KEY,
    boundary_code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    admin_level SMALLINT NOT NULL CHECK (admin_level BETWEEN 1 AND 3),
    parent_code VARCHAR(50),
    province_name VARCHAR(255),
    location_id BIGINT REFERENCES locations(id),
    centroid_lat DOUBLE PRECISION,
    centroid_lng DOUBLE PRECISION,
    geometry JSONB,
    source VARCHAR(255) NOT NULL,
    effective_date DATE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (boundary_code, admin_level)
);

CREATE INDEX IF NOT EXISTS idx_admin_boundaries_level_name
    ON admin_boundaries(admin_level, normalized_name);

CREATE INDEX IF NOT EXISTS idx_admin_boundaries_parent_code
    ON admin_boundaries(parent_code);

CREATE INDEX IF NOT EXISTS idx_admin_boundaries_location_id
    ON admin_boundaries(location_id);

CREATE INDEX IF NOT EXISTS idx_admin_boundaries_province_name
    ON admin_boundaries(province_name);
