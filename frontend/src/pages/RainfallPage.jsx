import { useEffect, useMemo, useState } from "react";
import { Bar, Doughnut, Line } from "react-chartjs-2";

import "../components/chartSetup";
import { apiClient } from "../api/client";
import StatCard from "../components/StatCard";
import SyncProgressModal from "../components/SyncProgressModal";
import { useAuth } from "../context/AuthContext";
import { toVietnameseLabel } from "../utils/viText";

const DEFAULT_LOCATION = { id: 1, name: "Quảng Trị", province: "Quảng Trị" };

function classifyRainfall(value) {
  const v = Number(value);
  if (v < 2) {
    return {
      level: "Không mưa",
      desc: "Độ ẩm đất giảm nhanh. Nguy cơ khô hạn nếu kéo dài."
    };
  }
  if (v < 10) {
    return {
      level: "Mưa nhẹ",
      desc: "Giảm nhiệt tạm thời, nhưng chưa bổ sung nước đáng kể."
    };
  }
  if (v < 30) {
    return {
      level: "Mưa vừa",
      desc: "Điều kiện thuận lợi cho canh tác và phục hồi độ ẩm đất."
    };
  }
  if (v < 50) {
    return {
      level: "Mưa lớn",
      desc: "Cần theo dõi ngập cục bộ và xói mòn tại khu vực dốc."
    };
  }
  return {
    level: "Mưa rất lớn",
    desc: "Rủi ro cao về lũ quét, sạt lở và ngập úng."
  };
}

export default function RainfallPage() {
  const { logActivity } = useAuth();
  const [locations, setLocations] = useState([]);
  const [form, setForm] = useState({
    locationId: "1",
    province: "Quảng Trị",
    startDate: "2020-01-01",
    endDate: "2020-12-31"
  });
  const [geeOnline, setGeeOnline] = useState(false);
  const [status, setStatus] = useState("");
  const [statusType, setStatusType] = useState("ok");
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [stats, setStats] = useState(null);
  const [dailyData, setDailyData] = useState([]);
  const [monthlyData, setMonthlyData] = useState([]);
  const locationOptions = locations.length > 0 ? locations : [DEFAULT_LOCATION];

  useEffect(() => {
    void logActivity("page_view", "rainfall");
  }, [logActivity]);

  const loadLocations = async () => {
    try {
      const response = await apiClient.get("/locations");
      const next = response.data?.data || [];
      if (next.length > 0) {
        setLocations(next);
        setForm((prev) => ({
          ...prev,
          locationId: String(next[0].id),
          province: toVietnameseLabel(next[0].province)
        }));
      } else {
        setLocations([DEFAULT_LOCATION]);
        setForm((prev) => ({
          ...prev,
          locationId: String(DEFAULT_LOCATION.id),
          province: DEFAULT_LOCATION.province
        }));
        setStatus("Chưa có dữ liệu địa điểm trong CSDL, đang dùng địa điểm mặc định Quảng Trị.");
        setStatusType("warn");
      }
    } catch {
      setLocations([DEFAULT_LOCATION]);
      setForm((prev) => ({
        ...prev,
        locationId: String(DEFAULT_LOCATION.id),
        province: DEFAULT_LOCATION.province
      }));
      setStatus("Không tải được danh sách địa điểm, hệ thống dùng cấu hình mặc định.");
      setStatusType("warn");
    }
  };

  const checkGEEStatus = async () => {
    try {
      const response = await apiClient.get("/gee/status");
      const online = response.data?.data?.status === "online" && response.data?.data?.gee_initialized;
      setGeeOnline(Boolean(online));
    } catch {
      setGeeOnline(false);
    }
  };

  useEffect(() => {
    void loadLocations();
    void checkGEEStatus();
    const timer = window.setInterval(() => {
      void checkGEEStatus();
    }, 30000);
    return () => window.clearInterval(timer);
  }, []);

  const loadData = async (source = "gee") => {
    setLoading(true);
    setStatus("");
    try {
      const year = form.startDate.split("-")[0];
      const [daily, monthly] = await Promise.all([
        apiClient.get("/rainfall", {
          params: { location_id: form.locationId, start: form.startDate, end: form.endDate, source, province: form.province }
        }),
        apiClient.get("/rainfall/monthly", {
          params: { location_id: form.locationId, year, source, province: form.province }
        })
      ]);
      setDailyData(daily.data?.data?.data || []);
      setStats(daily.data?.data?.statistics || null);
      setMonthlyData(monthly.data?.data?.monthly_data || []);
      setStatus(source === "db" ? "Đã tải kết quả lượng mưa từ cơ sở dữ liệu." : "Đã cập nhật kết quả phân tích lượng mưa.");
      setStatusType("ok");
    } catch (err) {
      setStatus(err.response?.data?.error?.message || "Không tải được dữ liệu trong khoảng thời gian đã chọn.");
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  };

  const fetchFromGEE = async () => {
    if (!geeOnline) {
      setStatus("GEE service đang offline. Cần khởi động backend/scripts/api_server.py.");
      setStatusType("error");
      return;
    }
    setLoading(true);
    setSyncing(true);
    setStatus("");
    try {
      const response = await apiClient.post("/gee/fetch", {
        province: form.province,
        location_id: Number(form.locationId),
        start_date: form.startDate,
        end_date: form.endDate,
        data_types: ["rainfall"]
      });
      const records = response.data?.data?.results?.rainfall?.records || 0;
      setStatus(`Đồng bộ thành công ${records} bản ghi lượng mưa.`);
      setStatusType("ok");
      await loadData("db");
    } catch (err) {
      setStatus(err.response?.data?.error?.message || "Đồng bộ GEE thất bại.");
      setStatusType("error");
    } finally {
      setSyncing(false);
      setLoading(false);
    }
  };

  const alertInfo = useMemo(() => {
    if (!stats) {
      return null;
    }
    return classifyRainfall(stats.average);
  }, [stats]);

  const lineData = {
    labels: dailyData.map((item) => item.date),
    datasets: [
      {
        label: "Lượng mưa (mm)",
        data: dailyData.map((item) => Number(item.rainfall_mm || 0)),
        borderColor: "#0077b6",
        backgroundColor: "rgba(0, 119, 182, 0.15)",
        fill: true,
        tension: 0.3
      }
    ]
  };

  const monthlyChartData = {
    labels: monthlyData.map((item) => `T${item.month}`),
    datasets: [
      {
        label: "Tổng mưa (mm)",
        data: monthlyData.map((item) => Number(item.total || 0)),
        backgroundColor: "#00a676"
      }
    ]
  };

  const distributionCounts = dailyData.reduce(
    (acc, item) => {
      const value = Number(item.rainfall_mm || 0);
      if (value < 5) {
        acc[0] += 1;
      } else if (value < 10) {
        acc[1] += 1;
      } else if (value < 20) {
        acc[2] += 1;
      } else if (value < 50) {
        acc[3] += 1;
      } else {
        acc[4] += 1;
      }
      return acc;
    },
    [0, 0, 0, 0, 0]
  );

  const doughnutData = {
    labels: ["0-5", "5-10", "10-20", "20-50", ">50"],
    datasets: [
      {
        data: distributionCounts,
        backgroundColor: ["#caf0f8", "#90e0ef", "#48cae4", "#00b4d8", "#0077b6"]
      }
    ]
  };

  return (
    <>
      <SyncProgressModal
        open={syncing}
        title="Đang tải dữ liệu lượng mưa từ GEE"
        description="Hệ thống đang kết nối Google Earth Engine, lấy dữ liệu CHIRPS và đồng bộ vào cơ sở dữ liệu."
      />
      <section className="card page-header">
        <h1>Phân tích Lượng mưa</h1>
        <p>Dữ liệu CHIRPS và thống kê theo khoảng thời gian tùy chọn.</p>
      </section>

      {status && <div className={`status ${statusType}`}>{status}</div>}
      <div className={`status ${geeOnline ? "ok" : "warn"}`}>
        GEE Service: {geeOnline ? "Online" : "Offline"}
      </div>

      <section className="card controls">
        <div className="field">
          <label>Địa điểm</label>
          <select
            value={form.locationId}
            onChange={(e) => {
              const loc = locationOptions.find((item) => String(item.id) === e.target.value);
              setForm((prev) => ({
                ...prev,
                locationId: e.target.value,
                province: toVietnameseLabel(loc?.province || prev.province)
              }));
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
          <button type="button" className="btn btn-secondary" onClick={fetchFromGEE} disabled={loading || !geeOnline}>
            Tải từ GEE
          </button>
          <button type="button" className="btn btn-primary" onClick={loadData} disabled={loading || !geeOnline}>
            {loading ? "Đang phân tích..." : "Phân tích"}
          </button>
        </div>
      </section>

      {alertInfo && (
        <section className="alert-banner">
          <h3>{alertInfo.level}</h3>
          <p style={{ margin: 0 }}>{alertInfo.desc}</p>
        </section>
      )}

      <section className="grid-4">
        <StatCard label="Tổng lượng mưa (mm)" value={stats?.total ?? "--"} />
        <StatCard label="Trung bình (mm/ngày)" value={stats?.average ?? "--"} />
        <StatCard label="Lớn nhất (mm)" value={stats?.max ?? "--"} />
        <StatCard label="Số ngày dữ liệu" value={stats?.days ?? "--"} />
      </section>

      <section className="chart-grid">
        <div className="card chart-card">
          <h3>Lượng mưa theo thời gian</h3>
          <Line data={lineData} />
        </div>
      </section>
      <section className="chart-grid two">
        <div className="card chart-card">
          <h3>Tổng lượng mưa theo tháng</h3>
          <Bar data={monthlyChartData} />
        </div>
        <div className="card chart-card">
          <h3>Phân bố lượng mưa</h3>
          <Doughnut data={doughnutData} />
        </div>
      </section>
    </>
  );
}
