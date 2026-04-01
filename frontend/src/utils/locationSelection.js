const STORAGE_KEY = "gis:selected-location";

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function readSelectedLocation() {
  if (!canUseStorage()) {
    return null;
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function writeSelectedLocation(location) {
  if (!canUseStorage() || !location) {
    return;
  }

  const payload = {
    id: Number(location.id),
    name: location.name,
    province: location.province,
    geometry: location.geometry ?? null,
    boundaryCode: location.boundaryCode ?? null,
    adminLevel: location.adminLevel ?? null,
    parentCode: location.parentCode ?? null,
    centroid_lat: location.centroid_lat ?? null,
    centroid_lng: location.centroid_lng ?? null,
  };

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

export function pickPreferredLocation(locations, fallbackLocation) {
  const stored = readSelectedLocation();
  const pool = locations.length > 0 ? locations : [fallbackLocation];

  if (stored?.id) {
    const match = pool.find((item) => Number(item.id) === Number(stored.id));
    if (match) {
      return match;
    }
  }

  if (stored?.boundaryCode) {
    const match = pool.find((item) => String(item.boundaryCode || "") === String(stored.boundaryCode));
    if (match) {
      return match;
    }
  }

  return pool[0] || fallbackLocation;
}
