import argparse
import json
import os
import sys
import unicodedata
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"


def load_environment():
    load_dotenv(ROOT_DIR / ".env")
    load_dotenv(BACKEND_DIR / ".env", override=True)


def normalize_text(value):
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return " ".join(text.lower().strip().split())


def collect_points(value, output=None):
    if output is None:
        output = []
    if not isinstance(value, list):
        return output
    if len(value) >= 2 and isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)):
        output.append((float(value[0]), float(value[1])))
        return output
    for item in value:
        collect_points(item, output)
    return output


def compute_centroid(geometry):
    if not geometry:
        return None, None
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    points = collect_points(coordinates, [])
    if not points:
        return None, None
    lng = sum(point[0] for point in points) / len(points)
    lat = sum(point[1] for point in points) / len(points)
    return lat, lng


def read_geojson(input_path):
    with open(input_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if payload.get("type") == "FeatureCollection":
        return payload.get("features", [])
    if payload.get("type") == "Feature":
        return [payload]
    raise ValueError("Input file must be a GeoJSON FeatureCollection or Feature.")


def get_property(properties, property_names, fallback=None):
    for name in property_names:
        if name in properties and properties[name] not in (None, ""):
            return properties[name]
    return fallback


def open_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", ""),
        dbname=os.getenv("DB_NAME", "web_gis"),
    )


def upsert_location(cursor, name, province_name, geometry):
    cursor.execute(
        """
        SELECT id
        FROM locations
        WHERE LOWER(name) = LOWER(%s)
          AND LOWER(province) = LOWER(%s)
        ORDER BY id
        LIMIT 1
        """,
        (name, province_name),
    )
    row = cursor.fetchone()
    if row:
        cursor.execute(
            """
            UPDATE locations
            SET geometry = %s
            WHERE id = %s
            """,
            (json.dumps(geometry) if geometry else None, row[0]),
        )
        return row[0]

    cursor.execute(
        """
        INSERT INTO locations (name, province, geometry)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (name, province_name, json.dumps(geometry) if geometry else None),
    )
    return cursor.fetchone()[0]


def upsert_boundary(cursor, payload):
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
        VALUES (
            %(boundary_code)s,
            %(name)s,
            %(normalized_name)s,
            %(admin_level)s,
            %(parent_code)s,
            %(province_name)s,
            %(location_id)s,
            %(centroid_lat)s,
            %(centroid_lng)s,
            %(geometry)s,
            %(source)s,
            %(effective_date)s,
            %(metadata)s,
            NOW()
        )
        ON CONFLICT (boundary_code, admin_level)
        DO UPDATE SET
            name = EXCLUDED.name,
            normalized_name = EXCLUDED.normalized_name,
            parent_code = EXCLUDED.parent_code,
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
        payload,
    )


def build_parser():
    parser = argparse.ArgumentParser(description="Import Vietnam administrative boundaries GeoJSON into PostgreSQL.")
    parser.add_argument("--input", required=True, help="Path to a GeoJSON FeatureCollection.")
    parser.add_argument("--level", required=True, type=int, choices=[1, 2, 3], help="Administrative level: 1/2/3.")
    parser.add_argument("--name-property", default="name,NAME_1,NAME_2,NAME_3,ten", help="Comma-separated property candidates.")
    parser.add_argument("--code-property", default="code,id,ma,ADM1_PCODE,ADM2_PCODE,ADM3_PCODE", help="Comma-separated property candidates.")
    parser.add_argument("--parent-property", default="parent_code,province_code,district_code,ADM1_PCODE,ADM2_PCODE", help="Comma-separated property candidates.")
    parser.add_argument("--province-property", default="province_name,province,NAME_1,tinh", help="Comma-separated property candidates.")
    parser.add_argument("--source", required=True, help="Human-readable source label, for example linhbx/vietnam-topojson.")
    parser.add_argument("--effective-date", default="2025-07-01", help="Effective date of this dataset, default 2025-07-01.")
    parser.add_argument("--sync-locations", action="store_true", help="Upsert level-1 boundaries into locations and store location_id.")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    load_environment()
    features = read_geojson(args.input)

    name_fields = [item.strip() for item in args.name_property.split(",") if item.strip()]
    code_fields = [item.strip() for item in args.code_property.split(",") if item.strip()]
    parent_fields = [item.strip() for item in args.parent_property.split(",") if item.strip()]
    province_fields = [item.strip() for item in args.province_property.split(",") if item.strip()]

    imported = 0
    synced_locations = 0

    try:
        connection = open_connection()
    except psycopg2.Error as exc:
        print(f"Failed to connect to PostgreSQL: {exc}", file=sys.stderr)
        return 1

    with connection:
        with connection.cursor() as cursor:
            for index, feature in enumerate(features, start=1):
                properties = feature.get("properties", {})
                geometry = feature.get("geometry")

                name = get_property(properties, name_fields)
                if not name:
                    print(f"Skipping feature #{index}: missing name property.", file=sys.stderr)
                    continue

                boundary_code = str(get_property(properties, code_fields, fallback=f"L{args.level}-{index:05d}"))
                parent_code = get_property(properties, parent_fields)
                province_name = get_property(properties, province_fields)
                if args.level == 1 and not province_name:
                    province_name = name

                centroid_lat, centroid_lng = compute_centroid(geometry)
                location_id = None

                if args.sync_locations and args.level == 1:
                    location_id = upsert_location(cursor, str(name), str(province_name or name), geometry)
                    synced_locations += 1

                feature_payload = feature if feature.get("type") == "Feature" else {
                    "type": "Feature",
                    "properties": properties,
                    "geometry": geometry,
                }

                payload = {
                    "boundary_code": boundary_code,
                    "name": str(name),
                    "normalized_name": normalize_text(name),
                    "admin_level": args.level,
                    "parent_code": str(parent_code) if parent_code not in (None, "") else None,
                    "province_name": str(province_name) if province_name not in (None, "") else None,
                    "location_id": location_id,
                    "centroid_lat": centroid_lat,
                    "centroid_lng": centroid_lng,
                    "geometry": json.dumps(feature_payload, ensure_ascii=False),
                    "source": args.source,
                    "effective_date": args.effective_date,
                    "metadata": json.dumps(properties, ensure_ascii=False),
                }
                upsert_boundary(cursor, payload)
                imported += 1

    print(f"Imported {imported} administrative boundaries from {args.input}.")
    if args.sync_locations:
        print(f"Synchronized {synced_locations} level-1 boundaries into locations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
