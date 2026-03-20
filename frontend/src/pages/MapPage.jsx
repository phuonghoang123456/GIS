import { Fragment, useEffect, useMemo, useState } from "react";
import { ArrowRight, LoaderCircle, PencilLine, Target, Upload, X } from "lucide-react";
import {
  CircleMarker,
  GeoJSON,
  MapContainer,
  Polygon,
  Polyline,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
  ZoomControl,
} from "react-leaflet";
import { useNavigate } from "react-router-dom";

import { apiClient, authHeaders } from "../api/client";
import { useAuth } from "../context/AuthContext";
import {
  buildGeometryAnalysisScope,
  buildLocationAnalysisScope,
  readSelectedAnalysisScope,
  writeSelectedAnalysisScope,
} from "../utils/analysisScope";
import { getLocationCenter, getMapLabel, hasGeometry, normalizeGeoJson } from "../utils/mapGeometry";
import { pickPreferredLocation, writeSelectedLocation } from "../utils/locationSelection";
import { toVietnameseLabel } from "../utils/viText";

const DEFAULT_LOCATION = { id: 1, name: "Quảng Trị", province: "Quảng Trị", geometry: null, adminLevel: 1 };
const DEFAULT_CENTER = [16.75, 107.18];

function boundaryToLocation(boundary, availableLocations = []) {
  const matchedLocation = availableLocations.find(
    (item) =>
      String(item.name || "").toLowerCase() === String(boundary.name || "").toLowerCase() ||
      String(item.province || "").toLowerCase() === String(boundary.province_name || boundary.name || "").toLowerCase()
  );
  return {
    id: boundary.location_id || matchedLocation?.id || boundary.id,
    locationId: boundary.location_id || matchedLocation?.id || null,
    boundaryCode: boundary.boundary_code,
    adminLevel: Number(boundary.admin_level || 1),
    parentCode: boundary.parent_code || null,
    name: boundary.name,
    province: boundary.province_name || boundary.name,
    geometry: boundary.geometry ?? null,
    centroid_lat: boundary.centroid_lat,
    centroid_lng: boundary.centroid_lng,
    source: boundary.source,
  };
}

function standardWardToLocation(ward, province) {
  return {
    id: `${ward.code}-${province?.boundaryCode || province?.id || "ward"}`,
    locationId: province?.locationId || province?.id || null,
    boundaryCode: ward.code,
    adminLevel: 2,
    parentCode: ward.province_code || province?.boundaryCode || null,
    name: ward.name,
    province: province?.name || province?.province || "",
    geometry: null,
    centroid_lat: province?.centroid_lat ?? null,
    centroid_lng: province?.centroid_lng ?? null,
    source: "thanglequoc/vietnamese-provinces-database",
  };
}

function countGeometryItems(items) {
  return items.filter((item) => hasGeometry(item)).length;
}

function resolveProvinceFromPreferred(pool, preferred) {
  return (
    pool.find((item) => String(item.boundaryCode || "") === String(preferred?.boundaryCode || "")) ||
    pool.find((item) => String(item.name || "").toLowerCase() === String(preferred?.province || preferred?.name || "").toLowerCase()) ||
    pool[0] ||
    DEFAULT_LOCATION
  );
}

function buildPolygonFeature(points, properties = {}) {
  if (!Array.isArray(points) || points.length < 3) return null;
  const coordinates = points.map(([lat, lng]) => [lng, lat]);
  return {
    type: "Feature",
    properties,
    geometry: { type: "Polygon", coordinates: [[...coordinates, coordinates[0]]] },
  };
}

function historyRowToScope(row) {
  return buildGeometryAnalysisScope({
    name: row.name,
    province: row.province_name,
    geometry: row.geometry,
    sourceType: row.source_type,
    boundaryCode: row.boundary_code,
    historyId: row.id,
    locationId: row.location_id,
    centroid_lat: row.centroid_lat,
    centroid_lng: row.centroid_lng,
  });
}

function readGeoJsonFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        resolve(JSON.parse(reader.result));
      } catch {
        reject(new Error("Tệp GeoJSON không hợp lệ."));
      }
    };
    reader.onerror = () => reject(new Error("Không đọc được tệp GeoJSON."));
    reader.readAsText(file, "utf-8");
  });
}

function MapFocusController({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo(center, zoom, { animate: true, duration: 1.1 });
  }, [center, map, zoom]);
  return null;
}

function MapDrawRecorder({ active, onPointAdd }) {
  useMapEvents({
    click(event) {
      if (active) onPointAdd([event.latlng.lat, event.latlng.lng]);
    },
  });
  return null;
}

export default function MapPage() {
  const navigate = useNavigate();
  const { logActivity, token } = useAuth();
  const [provinces, setProvinces] = useState([]);
  const [wardMap, setWardMap] = useState({});
  const [selectedProvinceCode, setSelectedProvinceCode] = useState("");
  const [selectedWardCode, setSelectedWardCode] = useState("");
  const [selectedLocation, setSelectedLocation] = useState(DEFAULT_LOCATION);
  const [customScope, setCustomScope] = useState(null);
  const [customName, setCustomName] = useState("Vùng phân tích tùy chọn");
  const [drawMode, setDrawMode] = useState(false);
  const [drawPoints, setDrawPoints] = useState([]);
  const [recentAreas, setRecentAreas] = useState([]);
  const [status, setStatus] = useState("");
  const [statusType, setStatusType] = useState("ok");
  const [isWardLoading, setIsWardLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    void logActivity("page_view", "map");
    const storedScope = readSelectedAnalysisScope();
    if (storedScope?.mode === "geometry" && storedScope.geometry) {
      setCustomScope(buildGeometryAnalysisScope(storedScope));
      setCustomName(storedScope.name || "Vùng phân tích tùy chọn");
    }
  }, [logActivity]);

  useEffect(() => {
    const loadHistory = async () => {
      if (!token) return;
      setHistoryLoading(true);
      try {
        const response = await apiClient.get("/analysis-areas/history", {
          params: { limit: 8 },
          headers: authHeaders(token),
        });
        setRecentAreas(response.data?.data || []);
      } catch {
        setRecentAreas([]);
      } finally {
        setHistoryLoading(false);
      }
    };
    void loadHistory();
  }, [token]);

  useEffect(() => {
    const loadProvinces = async () => {
      try {
        const locationResponse = await apiClient.get("/locations");
        const baseLocations = locationResponse.data?.data || [];
        let provinceBoundaries = [];
        try {
          const boundaryResponse = await apiClient.get("/boundaries", {
            params: { level: 1, include_geometry: true, limit: 5000 },
          });
          provinceBoundaries = (boundaryResponse.data?.data || []).map((item) => boundaryToLocation(item, baseLocations));
        } catch {
          provinceBoundaries = [];
        }

        const nextProvinces = provinceBoundaries.length
          ? provinceBoundaries
          : baseLocations.map((item) => ({ ...item, locationId: item.id, adminLevel: 1, boundaryCode: null, parentCode: null }));
        const preferred = pickPreferredLocation(nextProvinces, DEFAULT_LOCATION);
        const nextProvince = resolveProvinceFromPreferred(nextProvinces, preferred);
        setProvinces(nextProvinces);
        setSelectedProvinceCode(nextProvince?.boundaryCode || "");
        setSelectedLocation(nextProvince);
        writeSelectedLocation(nextProvince);
        if (!customScope) writeSelectedAnalysisScope(buildLocationAnalysisScope(nextProvince));
        setStatus(
          provinceBoundaries.length
            ? `Đã nạp ${nextProvinces.length} tỉnh/thành lên bản đồ. Bạn có thể click ranh giới, vẽ polygon tay hoặc upload GeoJSON.`
            : "Bản đồ đang dùng danh sách địa điểm hiện có, chưa lấy được đầy đủ admin_boundaries cấp tỉnh."
        );
        setStatusType(provinceBoundaries.length ? "ok" : "warn");
      } catch {
        setProvinces([DEFAULT_LOCATION]);
        setSelectedLocation(DEFAULT_LOCATION);
        setStatus("Không tải được dữ liệu bản đồ. Hệ thống đang dùng cấu hình mặc định của Quảng Trị.");
        setStatusType("error");
      }
    };
    void loadProvinces();
  }, [customScope]);

  const selectedProvince = useMemo(() => {
    if (!provinces.length) return DEFAULT_LOCATION;
    return provinces.find((item) => String(item.boundaryCode || "") === String(selectedProvinceCode || "")) || provinces[0];
  }, [provinces, selectedProvinceCode]);

  const wards = useMemo(() => wardMap[selectedProvinceCode] || [], [selectedProvinceCode, wardMap]);
  const selectedWard = useMemo(
    () => wards.find((item) => String(item.boundaryCode || "") === String(selectedWardCode || "")) || null,
    [selectedWardCode, wards]
  );

  useEffect(() => {
    const loadWards = async () => {
      if (!selectedProvince?.boundaryCode || wardMap[selectedProvince.boundaryCode]) return;
      setIsWardLoading(true);
      try {
        let wardItems = [];
        const boundaryResponse = await apiClient.get("/boundaries", {
          params: { level: 2, parent_code: selectedProvince.boundaryCode, include_geometry: true, limit: 5000 },
        });
        wardItems = (boundaryResponse.data?.data || []).map((item) => boundaryToLocation(item));
        if (!wardItems.length) {
          const wardResponse = await apiClient.get("/standard/wards", {
            params: { province_code: selectedProvince.boundaryCode, limit: 5000 },
          });
          wardItems = (wardResponse.data?.data || []).map((item) => standardWardToLocation(item, selectedProvince));
        }
        setWardMap((current) => ({ ...current, [selectedProvince.boundaryCode]: wardItems }));
      } catch {
        setWardMap((current) => ({ ...current, [selectedProvince.boundaryCode]: [] }));
      } finally {
        setIsWardLoading(false);
      }
    };
    setSelectedWardCode("");
    void loadWards();
  }, [selectedProvince, wardMap]);

  useEffect(() => {
    if (!customScope) setSelectedLocation(selectedWard || selectedProvince || DEFAULT_LOCATION);
  }, [customScope, selectedProvince, selectedWard]);

  const applyGeometryScope = (scope) => {
    const normalized = buildGeometryAnalysisScope(scope);
    if (!normalized) return;
    setCustomScope(normalized);
    setSelectedLocation(normalized);
    setDrawMode(false);
    setDrawPoints([]);
    writeSelectedAnalysisScope(normalized);
  };

  const selectedCenter = getLocationCenter(customScope || selectedWard || selectedProvince || selectedLocation || DEFAULT_LOCATION);
  const selectedZoom = customScope ? 11 : selectedWard ? 11 : hasGeometry(selectedProvince) ? 8 : 7;
  const wardsWithGeometry = countGeometryItems(wards);
  const drawingPreview = drawPoints.length >= 3 ? buildPolygonFeature(drawPoints) : null;

  const handleSelectProvince = async (province) => {
    setSelectedProvinceCode(province.boundaryCode || "");
    setSelectedWardCode("");
    setSelectedLocation(province);
    setCustomScope(null);
    writeSelectedLocation(province);
    writeSelectedAnalysisScope(buildLocationAnalysisScope(province));
    try {
      await logActivity("map_select_province", "map", { provinceCode: province.boundaryCode, province: province.province });
    } catch {}
  };

  const handleSelectWard = async (ward) => {
    setSelectedWardCode(ward.boundaryCode || "");
    setSelectedLocation(ward);
    setCustomScope(null);
    writeSelectedLocation(selectedProvince);
    writeSelectedAnalysisScope(buildLocationAnalysisScope(selectedProvince));
    try {
      await logActivity("map_select_ward", "map", { wardCode: ward.boundaryCode, wardName: ward.name });
    } catch {}
  };

  const useSelectedBoundaryAsScope = () => {
    const target = selectedWard || selectedProvince;
    if (!target?.geometry) {
      setStatus("Khu vực đang chọn chưa có geometry để dùng làm vùng phân tích.");
      setStatusType("warn");
      return;
    }
    applyGeometryScope({
      name: target.name,
      province: target.province || selectedProvince?.name,
      geometry: target.geometry,
      sourceType: "boundary_click",
      boundaryCode: target.boundaryCode,
      centroid_lat: target.centroid_lat,
      centroid_lng: target.centroid_lng,
      locationId: target.locationId,
    });
    setCustomName(target.name);
    setStatus(`Đã chọn vùng ${toVietnameseLabel(target.name)} để phân tích theo geometry.`);
    setStatusType("ok");
  };

  const beginDrawMode = () => {
    setDrawMode(true);
    setDrawPoints([]);
    setCustomScope(null);
    setStatus("Chế độ vẽ vùng đã bật. Hãy click lên bản đồ để đặt các đỉnh polygon rồi bấm Hoàn tất vùng.");
    setStatusType("ok");
  };

  const finishDrawArea = () => {
    const feature = buildPolygonFeature(drawPoints, { name: customName });
    if (!feature) {
      setStatus("Cần ít nhất 3 đỉnh để tạo polygon.");
      setStatusType("warn");
      return;
    }
    applyGeometryScope({
      name: customName,
      province: selectedProvince?.name || selectedProvince?.province || customName,
      geometry: feature,
      sourceType: "manual_polygon",
    });
    setStatus("Đã tạo vùng polygon thủ công.");
    setStatusType("ok");
  };

  const clearCustomArea = () => {
    setCustomScope(null);
    setDrawMode(false);
    setDrawPoints([]);
    writeSelectedAnalysisScope(buildLocationAnalysisScope(selectedProvince || DEFAULT_LOCATION));
  };

  const saveCurrentAreaToHistory = async () => {
    if (!customScope || !token) return;
    try {
      const response = await apiClient.post(
        "/analysis-areas/history",
        {
          geometry: customScope.geometry,
          area_name: customScope.name,
          province: customScope.province,
          source_type: customScope.sourceType,
          boundary_code: customScope.boundaryCode,
          location_id: customScope.locationId,
        },
        { headers: authHeaders(token) }
      );
      const historyRow = response.data?.data;
      setRecentAreas((current) => [historyRow, ...current.filter((item) => item.id !== historyRow?.id)].slice(0, 8));
      applyGeometryScope({ ...customScope, historyId: historyRow?.id });
      setStatus("Đã lưu vùng phân tích vào lịch sử tài khoản.");
      setStatusType("ok");
    } catch (error) {
      setStatus(error.response?.data?.error?.message || "Không lưu được vùng phân tích vào lịch sử.");
      setStatusType("error");
    }
  };

  const handleGeoJsonUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const payload = await readGeoJsonFile(file);
      const nextName = file.name.replace(/\.[^.]+$/, "") || customName;
      setCustomName(nextName);
      applyGeometryScope({
        name: nextName,
        province: selectedProvince?.name || selectedProvince?.province || nextName,
        geometry: payload,
        sourceType: "geojson_upload",
      });
      setStatus("Đã nạp GeoJSON thành công.");
      setStatusType("ok");
    } catch (error) {
      setStatus(error.message || "GeoJSON không hợp lệ.");
      setStatusType("error");
    } finally {
      event.target.value = "";
    }
  };

  const openModule = (path) => {
    const scope = customScope ? buildGeometryAnalysisScope(customScope) : buildLocationAnalysisScope(selectedProvince || selectedLocation);
    if (scope) writeSelectedAnalysisScope(scope);
    writeSelectedLocation(selectedProvince || selectedLocation || DEFAULT_LOCATION);
    navigate(path);
  };

  return (
    <div className="panel-stack">
      <section className="card page-header">
        <h1>Bản đồ WebGIS</h1>
        <p>Click vùng hành chính, vẽ polygon tay hoặc upload GeoJSON để tạo vùng phân tích linh hoạt cho mưa, nhiệt độ, NDVI và TVDI.</p>
      </section>
      {status && <div className={`status ${statusType}`}>{status}</div>}

      <section className="card map-toolbar">
        <div className="field">
          <label htmlFor="map-province">Tỉnh/Thành</label>
          <select id="map-province" value={selectedProvinceCode || ""} onChange={(e) => {
            const province = provinces.find((item) => String(item.boundaryCode || "") === e.target.value);
            if (province) void handleSelectProvince(province);
          }}>
            {provinces.map((province) => <option key={`province-option-${province.boundaryCode || province.id}`} value={province.boundaryCode || ""}>{toVietnameseLabel(province.name)}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="map-ward">Phường/Xã</label>
          <select id="map-ward" value={selectedWardCode || ""} disabled={!selectedProvince?.boundaryCode || isWardLoading || !wards.length} onChange={(e) => {
            const ward = wards.find((item) => String(item.boundaryCode || "") === e.target.value);
            if (ward) void handleSelectWard(ward);
          }}>
            <option value="">{isWardLoading ? "Đang tải danh sách..." : "Chọn phường/xã để xem chi tiết"}</option>
            {wards.map((ward) => <option key={`ward-option-${ward.boundaryCode}`} value={ward.boundaryCode}>{toVietnameseLabel(ward.name)}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="custom-area-name">Tên vùng tùy chọn</label>
          <input id="custom-area-name" value={customName} onChange={(e) => setCustomName(e.target.value)} />
        </div>
        <div className="map-toolbar__meta">
          <span className="scope-pill province">Tầng tỉnh: {provinces.length}</span>
          <span className="scope-pill ward">Tầng phường/xã: {selectedProvince?.boundaryCode ? wards.length : 0}</span>
          {isWardLoading ? <span className="scope-pill loading"><LoaderCircle size={14} /> Đang tải lớp phường/xã</span> : null}
          {customScope ? <span className="scope-pill custom">Đang bật geometry mode</span> : null}
        </div>
      </section>

      <section className="card map-toolbelt">
        <div className="map-toolbelt__group">
          <button type="button" className="btn btn-secondary" onClick={useSelectedBoundaryAsScope}><Target size={16} /> Dùng vùng đang chọn</button>
          <button type="button" className="btn btn-secondary" onClick={beginDrawMode}><PencilLine size={16} /> Vẽ polygon tay</button>
          <button type="button" className="btn btn-secondary" onClick={finishDrawArea} disabled={drawPoints.length < 3}>Hoàn tất vùng</button>
          <button type="button" className="btn btn-secondary" onClick={clearCustomArea}><X size={16} /> Xóa vùng</button>
        </div>
        <div className="map-toolbelt__group">
          <label className="btn btn-secondary map-upload-button">
            <Upload size={16} /> Upload GeoJSON
            <input type="file" accept=".json,.geojson,application/geo+json,application/json" onChange={handleGeoJsonUpload} />
          </label>
          <button type="button" className="btn btn-primary" onClick={saveCurrentAreaToHistory} disabled={!customScope || !token}>Lưu vùng vào lịch sử</button>
        </div>
      </section>

      <section className="map-layout">
        <div className="card map-shell">
          <MapContainer center={selectedCenter || DEFAULT_CENTER} zoom={selectedZoom} zoomControl={false} className="map-canvas">
            <ZoomControl position="bottomright" />
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <MapFocusController center={selectedCenter || DEFAULT_CENTER} zoom={selectedZoom} />
            <MapDrawRecorder active={drawMode} onPointAdd={(point) => setDrawPoints((current) => [...current, point])} />
            {provinces.map((province) => {
              const center = getLocationCenter(province);
              const selected = String(selectedProvince?.boundaryCode || "") === String(province.boundaryCode || "");
              const geoJson = normalizeGeoJson(province.geometry);
              return (
                <Fragment key={`province-${province.boundaryCode || province.id}`}>
                  {geoJson ? <GeoJSON data={geoJson} eventHandlers={{ click: () => void handleSelectProvince(province) }} style={() => ({ color: selected ? "#0b5d7a" : "#00796b", weight: selected ? 3.2 : 1.8, fillColor: selected ? "#80deea" : "#a5d6a7", fillOpacity: selected ? 0.32 : 0.1 })} /> : null}
                  <CircleMarker center={center} radius={selected ? 9 : 6} pathOptions={{ color: selected ? "#0f2132" : "#0077b6", weight: 2, fillColor: selected ? "#f57c00" : "#00a676", fillOpacity: 0.92 }} eventHandlers={{ click: () => void handleSelectProvince(province) }}>
                    <Popup><strong>{toVietnameseLabel(province.name)}</strong><br />{hasGeometry(province) ? "Có ranh giới cấp tỉnh" : "Đang dùng điểm trung tâm"}</Popup>
                  </CircleMarker>
                </Fragment>
              );
            })}
            {wards.map((ward) => {
              const center = getLocationCenter(ward);
              const selected = String(selectedWard?.boundaryCode || "") === String(ward.boundaryCode || "");
              const geoJson = normalizeGeoJson(ward.geometry);
              return (
                <Fragment key={`ward-${ward.boundaryCode || ward.id}`}>
                  {geoJson ? <GeoJSON data={geoJson} eventHandlers={{ click: () => void handleSelectWard(ward) }} style={() => ({ color: selected ? "#ef6c00" : "#1565c0", weight: selected ? 2.4 : 1.4, fillColor: selected ? "#ffcc80" : "#bbdefb", fillOpacity: selected ? 0.38 : 0.18 })} /> : null}
                  <CircleMarker center={center} radius={selected ? 7 : 4} pathOptions={{ color: selected ? "#8d4f00" : "#1565c0", weight: 1.5, fillColor: selected ? "#ff9800" : "#90caf9", fillOpacity: 0.92 }} eventHandlers={{ click: () => void handleSelectWard(ward) }}>
                    <Popup><strong>{toVietnameseLabel(ward.name)}</strong><br />{toVietnameseLabel(ward.province)}</Popup>
                  </CircleMarker>
                </Fragment>
              );
            })}
            {drawPoints.length > 1 ? <Polyline positions={drawPoints} pathOptions={{ color: "#ef6c00", weight: 3 }} /> : null}
            {drawingPreview ? <Polygon positions={drawPoints} pathOptions={{ color: "#ef6c00", weight: 2.5, fillOpacity: 0.16 }} /> : null}
            {drawPoints.map((point, index) => <CircleMarker key={`draw-point-${index}`} center={point} radius={4} pathOptions={{ color: "#ef6c00", fillColor: "#ff9800", fillOpacity: 1 }} />)}
            {customScope?.geometry ? <GeoJSON data={normalizeGeoJson(customScope.geometry)} style={() => ({ color: "#8e24aa", weight: 3, fillColor: "#ce93d8", fillOpacity: 0.25 })} /> : null}
          </MapContainer>
        </div>

        <div className="panel-stack">
          <section className="card map-panel">
            <div className="map-panel__header">
              <div>
                <h3>{toVietnameseLabel((customScope || selectedWard || selectedProvince)?.name)}</h3>
                <p>{customScope ? `Vùng tùy chọn - ${toVietnameseLabel(customScope.province)}` : selectedWard ? `Thuộc ${toVietnameseLabel(selectedProvince?.name)}` : toVietnameseLabel((selectedProvince || DEFAULT_LOCATION).province)}</p>
              </div>
              <span className={`tag ${customScope ? "custom" : hasGeometry(customScope || selectedWard || selectedProvince) ? "ok" : "warn"}`}>{customScope ? "Geometry mode" : selectedWard ? "Cấp phường/xã" : "Cấp tỉnh"}</span>
            </div>
            <p className="map-panel__note">
              {customScope
                ? "Các mô-đun phân tích sẽ nhận trực tiếp geometry này thay vì chỉ location_id."
                : hasGeometry(selectedWard || selectedProvince)
                  ? "Bạn có thể chuyển ngay vùng đang chọn sang geometry mode bằng nút Dùng vùng đang chọn."
                  : "Khu vực này chưa có polygon riêng, hệ thống đang dùng point đại diện."}
            </p>
            <div className="map-actions">
              <button type="button" className="btn btn-primary" onClick={() => openModule("/rainfall")}>Mở phân tích mưa <ArrowRight size={16} /></button>
              <button type="button" className="btn btn-secondary" onClick={() => openModule("/temperature")}>Mở nhiệt độ</button>
              <button type="button" className="btn btn-secondary" onClick={() => openModule("/ndvi")}>Mở NDVI</button>
              <button type="button" className="btn btn-secondary" onClick={() => openModule("/tvdi")}>Mở TVDI</button>
            </div>
          </section>

          <section className="card map-panel">
            <div className="map-panel__header">
              <div><h3>Lớp phường/xã</h3><p>{toVietnameseLabel(selectedProvince?.name)}</p></div>
              <span className={`tag ${wardsWithGeometry > 0 ? "ok" : "warn"}`}>{wards.length} đối tượng</span>
            </div>
            <div className="location-list">
              {wards.map((ward) => {
                const selected = String(selectedWard?.boundaryCode || "") === String(ward.boundaryCode || "");
                return (
                  <button key={`ward-item-${ward.boundaryCode || ward.id}`} type="button" className={`location-item ${selected ? "active" : ""}`} onClick={() => void handleSelectWard(ward)}>
                    <div><strong>{toVietnameseLabel(ward.name)}</strong><span>{toVietnameseLabel(ward.province)}</span></div>
                    <span className={`tag ${hasGeometry(ward) ? "ok" : "warn"}`}>{hasGeometry(ward) ? "Polygon" : "Point"}</span>
                  </button>
                );
              })}
              {!isWardLoading && !wards.length ? <div className="location-list__empty">Chọn một tỉnh/thành có dữ liệu chi tiết để xem danh sách phường/xã.</div> : null}
            </div>
          </section>

          <section className="card map-panel">
            <div className="map-panel__header">
              <div><h3>Vùng gần đây</h3><p>Lưu theo tài khoản đăng nhập</p></div>
              <span className={`tag ${recentAreas.length > 0 ? "ok" : "warn"}`}>{historyLoading ? "Đang tải" : recentAreas.length}</span>
            </div>
            <div className="location-list">
              {recentAreas.map((item) => {
                const scope = historyRowToScope(item);
                const selected = String(customScope?.historyId || "") === String(item.id);
                return (
                  <button key={`history-area-${item.id}`} type="button" className={`location-item ${selected ? "active" : ""}`} onClick={() => { applyGeometryScope(scope); setCustomName(scope.name); }}>
                    <div><strong>{toVietnameseLabel(item.name)}</strong><span>{toVietnameseLabel(item.province_name)}</span></div>
                    <span className="tag custom">{item.source_type}</span>
                  </button>
                );
              })}
              {!historyLoading && !recentAreas.length ? <div className="location-list__empty">Chưa có vùng phân tích gần đây. Vẽ polygon hoặc upload GeoJSON rồi lưu để thấy danh sách này.</div> : null}
            </div>
          </section>
        </div>
      </section>
    </div>
  );
}
