import argparse
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from shapely import wkt
from shapely.geometry import mapping


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
DEFAULT_DATASET_ROOT = ROOT_DIR / "external" / "vietnamese-provinces-database"


def load_environment():
    load_dotenv(ROOT_DIR / ".env")
    load_dotenv(BACKEND_DIR / ".env", override=True)


def db_config():
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": os.getenv("DB_PORT", "5432"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASS", ""),
        "dbname": os.getenv("DB_NAME", "web_gis"),
    }


def connect():
    return psycopg2.connect(**db_config())


def run_sql_via_psql(sql_path):
    psql = shutil.which("psql")
    if not psql:
        return False

    config = db_config()
    env = os.environ.copy()
    env["PGPASSWORD"] = config["password"]
    command = [
        psql,
        "-h",
        config["host"],
        "-p",
        str(config["port"]),
        "-U",
        config["user"],
        "-d",
        config["dbname"],
        "-v",
        "ON_ERROR_STOP=1",
        "-f",
        str(sql_path),
    ]
    subprocess.run(command, check=True, env=env)
    return True


def run_sql_text(connection, sql_text):
    with connection.cursor() as cursor:
        cursor.execute(sql_text)
    connection.commit()


def run_sql_file(connection, sql_path):
    if run_sql_via_psql(sql_path):
        return
    sql_text = Path(sql_path).read_text(encoding="utf-8")
    run_sql_text(connection, sql_text)


def run_zipped_sql(connection, zip_path):
    with zipfile.ZipFile(zip_path, "r") as archive:
        entries = [entry for entry in archive.namelist() if entry.lower().endswith(".sql")]
        if not entries:
            raise RuntimeError(f"No SQL file found inside {zip_path}.")
        sql_name = entries[0]
        sql_text = archive.read(sql_name).decode("utf-8")

    psql = shutil.which("psql")
    if psql:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".sql", delete=False) as handle:
            handle.write(sql_text)
            temp_sql_path = Path(handle.name)
        try:
            run_sql_via_psql(temp_sql_path)
        finally:
            temp_sql_path.unlink(missing_ok=True)
        return

    run_sql_text(connection, sql_text)


def table_exists(cursor, table_name):
    cursor.execute("SELECT to_regclass(%s)", (table_name,))
    return cursor.fetchone()[0] is not None


def table_has_rows(cursor, table_name):
    if not table_exists(cursor, table_name):
        return False
    cursor.execute(f"SELECT EXISTS (SELECT 1 FROM {table_name} LIMIT 1)")
    return bool(cursor.fetchone()[0])


def execute_bootstrap_sql(connection):
    bootstrap_sql = BACKEND_DIR / "sql" / "bootstrap_admin_boundaries.sql"
    run_sql_file(connection, bootstrap_sql)


def reload_standard_tables(connection):
    drop_sql = """
    DROP TABLE IF EXISTS gis_wards CASCADE;
    DROP TABLE IF EXISTS gis_provinces CASCADE;
    DROP TABLE IF EXISTS wards CASCADE;
    DROP TABLE IF EXISTS provinces CASCADE;
    DROP TABLE IF EXISTS administrative_units CASCADE;
    DROP TABLE IF EXISTS administrative_regions CASCADE;
    """
    run_sql_text(connection, drop_sql)


def ensure_standard_dataset(connection, dataset_root, reload_standard=False, reload_gis=False):
    create_sql = dataset_root / "postgresql" / "postgres_CreateTables_vn_units.sql"
    import_sql = dataset_root / "postgresql" / "postgres_ImportData_vn_units.sql"

    with connection.cursor() as cursor:
        standard_ready = table_has_rows(cursor, "provinces") and table_has_rows(cursor, "wards")

    if reload_standard:
        reload_standard_tables(connection)
        standard_ready = False

    if not standard_ready:
        run_sql_file(connection, create_sql)
        run_sql_file(connection, import_sql)


def upsert_location(cursor, name, geometry_feature):
    cursor.execute(
        """
        SELECT id
        FROM locations
        WHERE LOWER(name) = LOWER(%s)
           OR LOWER(province) = LOWER(%s)
        ORDER BY id
        LIMIT 1
        """,
        (name, name),
    )
    row = cursor.fetchone()
    geometry_payload = json.dumps(geometry_feature, ensure_ascii=False) if geometry_feature else None

    if row:
        cursor.execute(
            """
            UPDATE locations
            SET name = %s,
                province = %s,
                geometry = %s
            WHERE id = %s
            """,
            (name, name, geometry_payload, row[0]),
        )
        return row[0]

    cursor.execute(
        """
        INSERT INTO locations (name, province, geometry)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (name, name, geometry_payload),
    )
    return cursor.fetchone()[0]


def build_feature(geometry_json, properties):
    if not geometry_json:
        return None
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": json.loads(geometry_json),
    }


def parse_gis_zip(dataset_root):
    zip_path = dataset_root / "postgresql" / "gis" / "postgresql_ImportData_gis.sql.zip"
    province_index = {}
    ward_index = {}

    with zipfile.ZipFile(zip_path, "r") as archive:
        entries = [entry for entry in archive.namelist() if entry.lower().endswith(".sql")]
        if not entries:
            raise RuntimeError(f"No SQL file found inside {zip_path}.")
        with archive.open(entries[0], "r") as handle:
            for raw_line in handle:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if line.startswith("INSERT INTO gis_provinces"):
                    code, feature, lat, lng = parse_gis_insert_line(line)
                    province_index[code] = {"feature": feature, "lat": lat, "lng": lng}
                elif line.startswith("INSERT INTO gis_wards"):
                    code, feature, lat, lng = parse_gis_insert_line(line)
                    ward_index[code] = {"feature": feature, "lat": lat, "lng": lng}

    return province_index, ward_index


def parse_gis_insert_line(line):
    code = line.split("VALUES ('", 1)[1].split("'", 1)[0]
    parts = line.split("ST_GeomFromText('")
    if len(parts) < 3:
        return code, None, None, None

    geom_wkt = parts[2].rsplit("', 4326", 1)[0]
    geometry = wkt.loads(geom_wkt)
    point = geometry.representative_point()
    feature = {
        "type": "Feature",
        "properties": {"code": code},
        "geometry": mapping(geometry),
    }
    return code, feature, float(point.y), float(point.x)


def sync_province_boundaries(connection, province_gis_index):
    synchronized = 0
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                p.code,
                p.name,
                p.name_en,
                p.full_name,
                p.full_name_en,
                p.code_name,
                p.administrative_unit_id,
                au.short_name,
                au.short_name_en
            FROM provinces p
            LEFT JOIN administrative_units au ON au.id = p.administrative_unit_id
            ORDER BY p.code
            """
        )
        provinces = cursor.fetchall()

        for row in provinces:
            (
                code,
                name,
                name_en,
                full_name,
                full_name_en,
                code_name,
                administrative_unit_id,
                unit_short_name,
                unit_short_name_en,
            ) = row
            gis_payload = province_gis_index.get(code, {})
            feature = gis_payload.get("feature")
            centroid_lat = gis_payload.get("lat")
            centroid_lng = gis_payload.get("lng")
            properties = {
                "code": code,
                "name": name,
                "name_en": name_en,
                "full_name": full_name,
                "full_name_en": full_name_en,
                "code_name": code_name,
                "administrative_unit_id": administrative_unit_id,
                "administrative_unit_name": unit_short_name,
                "administrative_unit_name_en": unit_short_name_en,
            }
            if feature:
                feature["properties"] = {**feature.get("properties", {}), **properties}
            location_id = upsert_location(cursor, name, feature)
            cursor.execute(
                """
                INSERT INTO admin_boundaries (
                    boundary_code,
                    name,
                    normalized_name,
                    admin_level,
                    parent_code,
                    province_name,
                    location_id,
                    centroid_lat,
                    centroid_lng,
                    geometry,
                    source,
                    effective_date,
                    metadata,
                    updated_at
                )
                VALUES (%s, %s, %s, 1, NULL, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, NOW())
                ON CONFLICT (boundary_code, admin_level)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    normalized_name = EXCLUDED.normalized_name,
                    province_name = EXCLUDED.province_name,
                    location_id = EXCLUDED.location_id,
                    centroid_lat = EXCLUDED.centroid_lat,
                    centroid_lng = EXCLUDED.centroid_lng,
                    geometry = EXCLUDED.geometry,
                    source = EXCLUDED.source,
                    effective_date = EXCLUDED.effective_date,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                """,
                (
                    code,
                    name,
                    code_name or name.lower(),
                    name,
                    location_id,
                    centroid_lat,
                    centroid_lng,
                    json.dumps(feature, ensure_ascii=False) if feature else None,
                    "thanglequoc/vietnamese-provinces-database",
                    "2025-07-01",
                    json.dumps(properties, ensure_ascii=False),
                ),
            )
            synchronized += 1
    connection.commit()
    return synchronized


def sync_ward_boundaries(connection, ward_gis_index):
    synchronized = 0
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                w.code,
                w.name,
                w.name_en,
                w.full_name,
                w.full_name_en,
                w.code_name,
                w.province_code,
                p.name AS province_name,
                w.administrative_unit_id,
                au.short_name,
                au.short_name_en
            FROM wards w
            LEFT JOIN provinces p ON p.code = w.province_code
            LEFT JOIN administrative_units au ON au.id = w.administrative_unit_id
            ORDER BY w.code
            """
        )
        wards = cursor.fetchall()

        for row in wards:
            (
                code,
                name,
                name_en,
                full_name,
                full_name_en,
                code_name,
                province_code,
                province_name,
                administrative_unit_id,
                unit_short_name,
                unit_short_name_en,
            ) = row
            gis_payload = ward_gis_index.get(code, {})
            feature = gis_payload.get("feature")
            centroid_lat = gis_payload.get("lat")
            centroid_lng = gis_payload.get("lng")
            properties = {
                "code": code,
                "name": name,
                "name_en": name_en,
                "full_name": full_name,
                "full_name_en": full_name_en,
                "code_name": code_name,
                "province_code": province_code,
                "province_name": province_name,
                "administrative_unit_id": administrative_unit_id,
                "administrative_unit_name": unit_short_name,
                "administrative_unit_name_en": unit_short_name_en,
            }
            if feature:
                feature["properties"] = {**feature.get("properties", {}), **properties}
            cursor.execute(
                """
                INSERT INTO admin_boundaries (
                    boundary_code,
                    name,
                    normalized_name,
                    admin_level,
                    parent_code,
                    province_name,
                    location_id,
                    centroid_lat,
                    centroid_lng,
                    geometry,
                    source,
                    effective_date,
                    metadata,
                    updated_at
                )
                VALUES (%s, %s, %s, 2, %s, %s, NULL, %s, %s, %s::jsonb, %s, %s, %s::jsonb, NOW())
                ON CONFLICT (boundary_code, admin_level)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    normalized_name = EXCLUDED.normalized_name,
                    parent_code = EXCLUDED.parent_code,
                    province_name = EXCLUDED.province_name,
                    centroid_lat = EXCLUDED.centroid_lat,
                    centroid_lng = EXCLUDED.centroid_lng,
                    geometry = EXCLUDED.geometry,
                    source = EXCLUDED.source,
                    effective_date = EXCLUDED.effective_date,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                """,
                (
                    code,
                    name,
                    code_name or name.lower(),
                    province_code,
                    province_name,
                    centroid_lat,
                    centroid_lng,
                    json.dumps(feature, ensure_ascii=False) if feature else None,
                    "thanglequoc/vietnamese-provinces-database",
                    "2025-07-01",
                    json.dumps(properties, ensure_ascii=False),
                ),
            )
            synchronized += 1
    connection.commit()
    return synchronized


def parser():
    arg_parser = argparse.ArgumentParser(description="Bootstrap standard Vietnam administrative tables from thanglequoc repo.")
    arg_parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT), help="Path to cloned vietnamese-provinces-database.")
    arg_parser.add_argument("--reload-standard", action="store_true", help="Drop and reload standard province/ward tables.")
    arg_parser.add_argument("--reload-gis", action="store_true", help="Drop and reload GIS tables from zipped SQL.")
    return arg_parser


def main():
    args = parser().parse_args()
    dataset_root = Path(args.dataset_root)
    if not dataset_root.exists():
        raise SystemExit(f"Dataset root not found: {dataset_root}")

    load_environment()
    connection = connect()
    try:
        execute_bootstrap_sql(connection)
        ensure_standard_dataset(connection, dataset_root, args.reload_standard, args.reload_gis)
        province_gis_index, ward_gis_index = parse_gis_zip(dataset_root)
        synced_provinces = sync_province_boundaries(connection, province_gis_index)
        synced_wards = sync_ward_boundaries(connection, ward_gis_index)
        print(f"Synchronized {synced_provinces} provinces and {synced_wards} wards into admin_boundaries.")
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
