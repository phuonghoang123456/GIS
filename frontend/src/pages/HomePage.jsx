import { useEffect, useMemo, useState } from "react";
import { Bar, Line } from "react-chartjs-2";
import { Link } from "react-router-dom";

import "../components/chartSetup";
import { apiClient } from "../api/client";
import StatCard from "../components/StatCard";
import { useAuth } from "../context/AuthContext";
import { pickPreferredLocation, writeSelectedLocation } from "../utils/locationSelection";
import { toVietnameseLabel } from "../utils/viText";

const DEFAULT_LOCATION = { id: 1, name: "Quảng Trị", province: "Quảng Trị" };

const quickLinks = [
  { to: "/rainfall", title: "Lượng mưa", description: "Theo dõi lượng mưa, so sánh giai đoạn và đối chiếu giữa các địa điểm." },
  { to: "/temperature", title: "Nhiệt độ", description: "Phân tích nhiệt độ theo ngày và biên độ theo tháng." },
  { to: "/soil-moisture", title: "Độ ẩm đất", description: "Quan sát độ ẩm bề mặt, tầng rễ và toàn hồ sơ đất." },
  { to: "/ndvi", title: "NDVI", description: "Đánh giá sức khỏe thảm thực vật và mức độ che phủ xanh." },
  { to: "/tvdi", title: "TVDI", description: "Theo dõi hạn hán, TVDI, LST và các đợt khô hạn nghiêm trọng." },
  { to: "/map", title: "Bản đồ WebGIS", description: "Xem vị trí, ranh giới và chọn nhanh địa điểm trực tiếp trên bản đồ." },
  { to: "/activity", title: "Hoạt động", description: "Xem lịch sử thao tác và thống kê sử dụng của tài khoản." }
];

export default function HomePage() {
  const { logActivity } = useAuth();
  const [locations, setLocations] = useState([]);
  const [form, setForm] = useState({
    locationId: "1",
    province: "Quảng Trị",
    startDate: "2020-01-01",
    endDate: "2020-12-31"
  });
  const [status, setStatus] = useState("");
  const [statusType, setStatusType] = useState("ok");
  const [overview, setOverview] = useState(null);
  const [timeseries, setTimeseries] = useState([]);
  const [loading, setLoading] = useState(false);
  const locationOptions = locations.length > 0 ? locations : [DEFAULT_LOCATION];

  useEffect(() => {
    void logActivity("page_view", "dashboard");
  }, [logActivity]);

  useEffect(() => {
    const loadLocations = async () => {
      try {
        const response = await apiClient.get("/locations");
        const next = response.data?.data || [];
        if (next.length > 0) {
          setLocations(next);
          const preferred = pickPreferredLocation(next, DEFAULT_LOCATION);
          writeSelectedLocation(preferred);
          setForm((prev) => ({
            ...prev,
            locationId: String(preferred.id),
            province: toVietnameseLabel(preferred.province)
          }));
        } else {
          setLocations([DEFAULT_LOCATION]);
          setStatus("Chưa có danh sách địa điểm trong CSDL, đang dùng mặc định Quảng Trị.");
          setStatusType("warn");
        }
      } catch {
        setLocations([DEFAULT_LOCATION]);
        setStatus("Không tải được danh sách địa điểm.");
        setStatusType("warn");
      }
    };
    void loadLocations();
  }, []);

  const loadDashboard = async () => {
    setLoading(true);
    setStatus("");
    try {
      const [overviewResponse, timeseriesResponse] = await Promise.all([
        apiClient.get("/dashboard/overview", {
          params: {
            location_id: form.locationId,
            start: form.startDate,
            end: form.endDate
          }
        }),
        apiClient.get("/dashboard/timeseries", {
          params: {
            location_id: form.locationId,
            start: form.startDate,
            end: form.endDate
          }
        })
      ]);
      setOverview(overviewResponse.data?.data || null);
      setTimeseries(timeseriesResponse.data?.data?.timeseries || []);
      setStatus("Đã cập nhật dashboard tổng quan.");
      setStatusType("ok");
    } catch (err) {
      setStatus(err.response?.data?.error?.message || "Không tải được dữ liệu dashboard.");
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (form.locationId) {
      void loadDashboard();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.locationId]);

  const climateSeries = useMemo(
    () => ({
      labels: timeseries.map((item) => item.date),
      datasets: [
        {
          label: "Lượng mưa (mm)",
          data: timeseries.map((item) => Number(item.rainfall_mm || 0)),
          borderColor: "#0077b6",
          backgroundColor: "rgba(0, 119, 182, 0.16)",
          fill: true,
          tension: 0.28
        },
        {
          label: "Nhiệt độ TB (°C)",
          data: timeseries.map((item) => Number(item.temp_mean || 0)),
          borderColor: "#d84315",
          tension: 0.28
        }
      ]
    }),
    [timeseries]
  );

  const ecosystemSeries = useMemo(
    () => ({
      labels: timeseries.map((item) => item.date),
      datasets: [
        {
          label: "NDVI",
          data: timeseries.map((item) => Number(item.ndvi_mean || 0)),
          borderColor: "#00a676",
          backgroundColor: "rgba(0, 166, 118, 0.14)",
          fill: true,
          tension: 0.28
        },
        {
          label: "TVDI",
          data: timeseries.map((item) => Number(item.tvdi_mean || 0)),
          borderColor: "#ef8a62",
          tension: 0.28
        }
      ]
    }),
    [timeseries]
  );

  const soilSeries = useMemo(
    () => ({
      labels: timeseries.map((item) => item.date),
      datasets: [
        {
          label: "Độ ẩm bề mặt",
          data: timeseries.map((item) => Number(item.sm_surface || 0)),
          backgroundColor: "#48cae4"
        },
        {
          label: "Độ ẩm tầng rễ",
          data: timeseries.map((item) => Number(item.sm_rootzone || 0)),
          backgroundColor: "#00a676"
        }
      ]
    }),
    [timeseries]
  );

  return (
    <div className="panel-stack">
      <section className="card page-header">
        <h1>Dashboard khí hậu tổng quan</h1>
        <p>
          Theo dõi nhanh lượng mưa, nhiệt độ, độ ẩm đất, NDVI và TVDI theo địa điểm và khoảng thời gian lựa chọn.
        </p>
      </section>

      {status && <div className={`status ${statusType}`}>{status}</div>}

      <section className="card controls">
        <div className="field">
          <label>Địa điểm</label>
          <select
            value={form.locationId}
            onChange={(e) => {
              const location = locationOptions.find((item) => String(item.id) === e.target.value);
              setForm((prev) => ({
                ...prev,
                locationId: e.target.value,
                province: toVietnameseLabel(location?.province || prev.province)
              }));
              if (location) {
                writeSelectedLocation(location);
              }
            }}
          >
            {locationOptions.map((location) => (
              <option key={location.id} value={location.id}>
                {toVietnameseLabel(location.name)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Từ ngày</label>
          <input
            type="date"
            value={form.startDate}
            onChange={(e) => setForm((prev) => ({ ...prev, startDate: e.target.value }))}
          />
        </div>
        <div className="field">
          <label>Đến ngày</label>
          <input
            type="date"
            value={form.endDate}
            onChange={(e) => setForm((prev) => ({ ...prev, endDate: e.target.value }))}
          />
        </div>
        <div className="actions">
          <button type="button" className="btn btn-primary" onClick={loadDashboard} disabled={loading}>
            {loading ? "Đang tải dashboard..." : "Làm mới dashboard"}
          </button>
        </div>
      </section>

      <section className="grid-4">
        <StatCard label="Tổng lượng mưa (mm)" value={overview?.rainfall?.total ?? "--"} />
        <StatCard label="Nhiệt độ TB (°C)" value={overview?.temperature?.average ?? "--"} />
        <StatCard label="Độ ẩm bề mặt" value={overview?.soil_moisture?.surface ?? "--"} />
        <StatCard label="NDVI TB" value={overview?.ndvi?.average ?? "--"} />
        <StatCard label="TVDI TB" value={overview?.tvdi?.average ?? "--"} />
        <StatCard label="Ngày hạn nặng" value={overview?.tvdi?.drought_days ?? "--"} />
      </section>

      <section className="chart-grid two">
        <div className="card chart-card">
          <h3>Diễn biến mưa và nhiệt độ</h3>
          <Line data={climateSeries} />
        </div>
        <div className="card chart-card">
          <h3>Diễn biến NDVI và TVDI</h3>
          <Line data={ecosystemSeries} />
        </div>
      </section>

      <section className="chart-grid">
        <div className="card chart-card">
          <h3>Độ ẩm đất bề mặt và tầng rễ</h3>
          <Bar data={soilSeries} />
        </div>
      </section>

      <section className="split-grid">
        <div className="card insight-card">
          <h3>Tóm tắt nhanh</h3>
          <p>
            Dashboard này đọc dữ liệu đã đồng bộ trong cơ sở dữ liệu. Nếu biểu đồ còn trống, hãy vào từng mô-đun và
            dùng chức năng <strong>Tải từ GEE</strong> để đồng bộ dữ liệu trước.
          </p>
        </div>
        <div className="card insight-card">
          <h3>Địa điểm đang theo dõi</h3>
          <p>
            Địa điểm hiện tại: <strong>{toVietnameseLabel(form.province)}</strong>. Bạn có thể đổi địa điểm phía trên
            để xem toàn bộ dashboard theo vùng khác.
          </p>
        </div>
      </section>

      <section className="chart-grid two">
        {quickLinks.map((item) => (
          <Link key={item.to} to={item.to} className="card chart-card" style={{ textDecoration: "none" }}>
            <h3>{item.title}</h3>
            <p className="muted-text">{item.description}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
