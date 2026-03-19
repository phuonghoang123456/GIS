from __future__ import annotations

from math import sqrt


def to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def fixed(value, digits: int = 2) -> str:
    return f"{to_float(value):.{digits}f}"


def calculate_trend(points: list[dict]) -> dict:
    if not points or len(points) < 2:
        return {"slope": 0, "trend": "insufficient_data"}

    n = len(points)
    sum_x = sum(p["x"] for p in points)
    sum_y = sum(p["y"] for p in points)
    sum_xy = sum(p["x"] * p["y"] for p in points)
    sum_x2 = sum(p["x"] * p["x"] for p in points)

    denominator = n * sum_x2 - sum_x * sum_x
    if denominator == 0:
        slope = 0
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denominator

    intercept = (sum_y - slope * sum_x) / n if n else 0

    trend = "stable"
    if slope > 0.5:
        trend = "increasing"
    elif slope < -0.5:
        trend = "decreasing"

    return {
        "slope": f"{slope:.4f}",
        "intercept": f"{intercept:.4f}",
        "trend": trend,
    }


def calculate_anomaly(current_value: float, historical_values: list[float]) -> dict:
    if not historical_values:
        return {"anomaly": 0, "percentage": 0, "z_score": 0}

    mean = sum(historical_values) / len(historical_values)
    variance = sum((v - mean) ** 2 for v in historical_values) / len(historical_values)
    std_dev = sqrt(variance)

    anomaly = current_value - mean
    percentage = (anomaly / mean) * 100 if mean else 0
    z_score = anomaly / std_dev if std_dev else 0

    return {
        "anomaly": f"{anomaly:.2f}",
        "percentage": f"{percentage:.2f}",
        "z_score": f"{z_score:.2f}",
    }


def classify_ndvi(value: float | None) -> dict:
    if value is None:
        return {"level": "unknown", "description": "Khong co du lieu", "color": "#999"}
    if value < 0:
        return {"level": "water", "description": "Nuoc/Khong thuc vat", "color": "#0571b0"}
    if value < 0.1:
        return {"level": "bare", "description": "Dat trong", "color": "#ca0020"}
    if value < 0.2:
        return {"level": "sparse", "description": "Thuc vat thua", "color": "#f4a582"}
    if value < 0.4:
        return {"level": "moderate", "description": "Thuc vat vua", "color": "#92c5de"}
    if value < 0.6:
        return {"level": "dense", "description": "Thuc vat day", "color": "#4dac26"}
    return {"level": "very_dense", "description": "Thuc vat rat day", "color": "#1b7837"}


def classify_tvdi(value: float | None) -> dict:
    if value is None:
        return {"level": "unknown", "description": "Khong co du lieu", "color": "#999"}
    if value < 0.2:
        return {"level": "wet", "description": "Am uot", "color": "#2166ac"}
    if value < 0.4:
        return {"level": "normal", "description": "Binh thuong", "color": "#67a9cf"}
    if value < 0.6:
        return {"level": "moderate", "description": "Han nhe", "color": "#fddbc7"}
    if value < 0.8:
        return {"level": "severe", "description": "Han nang", "color": "#ef8a62"}
    return {"level": "extreme", "description": "Han cuc doan", "color": "#b2182b"}
