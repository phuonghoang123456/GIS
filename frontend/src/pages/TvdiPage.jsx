import { useEffect, useMemo, useState } from "react";
import { Bar, Doughnut, Line } from "react-chartjs-2";

import "../components/chartSetup";
import { apiClient } from "../api/client";
import StatCard from "../components/StatCard";
import SyncProgressModal from "../components/SyncProgressModal";
import { useAuth } from "../context/AuthContext";
import { toVietnameseLabel } from "../utils/viText";

const DEFAULT_LOCATION = { id: 1, name: "Quảng Trị", province: "Quảng Trị" };

function classifyTvdi(value) {
  const v = Number(value);
  if (v < 0.2) {
    return { level: "Ẩm ướt", desc: "Không có dấu hiệu hạn hán đáng kể." };
  }
  if (v < 0.4) {
    return { level: "Bình thường", desc: "Điều kiện độ ẩm và nhiệt độ ổn định." };
  }
  if (v < 0.6) {
    return { level: "Hạn nhẹ", desc: "Cần tăng cường theo dõi nguồn nước tưới." };
  }
  if (v < 0.8) {
    return { level: "Hạn nặng", desc: "Nguy cơ giảm năng suất và cháy rừng tăng cao." };
  }
  return { level: "Hạn cực đoan", desc: "Tình huống khẩn cấp, cần kích hoạt phương án ứng phó." };
}

const droughtColors = ["#2166ac", "#67a9cf", "#fddbc7", "#ef8a62", "#b2182b"];

export default function TvdiPage() {
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
    void logActivity("page_view", "tvdi");
  }, [logActivity]);

  useEffect(() => {
    const boot = async () => {
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
        setStatus("Không tải được danh sách địa điểm.");
        setStatusType("warn");
      }
    };
    void boot();
  }, []);

  useEffect(() => {
    const check = async () => {
      try {
        const response = await apiClient.get("/gee/status");
        const online = response.data?.data?.status === "online" && response.data?.data?.gee_initialized;
        setGeeOnline(Boolean(online));
      } catch {
        setGeeOnline(false);
      }
    };
    void check();
    const timer = window.setInterval(() => void check(), 30000);
    return () => window.clearInterval(timer);
  }, []);

  const loadData = async (source = "gee") => {
    setLoading(true);
    setStatus("");
    try {
      const year = form.startDate.split("-")[0];
      const [daily, monthly] = await Promise.all([
        apiClient.get("/tvdi", {
          params: { location_id: form.locationId, start: form.startDate, end: form.endDate, source, province: form.province }
        }),
        apiClient.get("/tvdi/monthly", {
          params: { location_id: form.locationId, year, source, province: form.province }
        })
      ]);
      setDailyData(daily.data?.data?.data || []);
      setStats(daily.data?.data?.statistics || null);
      setMonthlyData(monthly.data?.data?.monthly_data || []);
      setStatus(source === "db" ? "Đã tải kết quả TVDI từ cơ sở dữ liệu." : "Đã cập nhật kết quả phân tích TVDI.");
      setStatusType("ok");
    } catch (err) {
      setStatus(err.response?.data?.error?.message || "Không tải được dữ liệu TVDI.");
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
        data_types: ["tvdi"]
      });
      const records = response.data?.data?.results?.tvdi?.records || 0;
      setStatus(`Đồng bộ thành công ${records} bản ghi TVDI.`);
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
    return classifyTvdi(stats.average);
  }, [stats]);

  const tvdiLineData = {
    labels: dailyData.map((item) => item.date),
    datasets: [
      {
        label: "TVDI trung bình",
        data: dailyData.map((item) => Number(item.tvdi_mean || 0)),
        borderColor: "#ef8a62",
        backgroundColor: "rgba(239, 138, 98, 0.15)",
        fill: true,
        tension: 0.3
      }
    ]
  };

  const monthlyChartData = {
    labels: monthlyData.map((item) => `T${item.month}`),
    datasets: [
      {
        label: "TVDI TB",
        data: monthlyData.map((item) => Number(item.avg_tvdi || 0)),
        backgroundColor: monthlyData.map((item) => {
          const v = Number(item.avg_tvdi || 0);
          if (v < 0.2) return droughtColors[0];
          if (v < 0.4) return droughtColors[1];
          if (v < 0.6) return droughtColors[2];
          if (v < 0.8) return droughtColors[3];
          return droughtColors[4];
        })
      }
    ]
  };

  const classCounts = dailyData.reduce(
    (acc, item) => {
      const v = Number(item.tvdi_mean || 0);
      if (v < 0.2) acc[0] += 1;
      else if (v < 0.4) acc[1] += 1;
      else if (v < 0.6) acc[2] += 1;
      else if (v < 0.8) acc[3] += 1;
      else acc[4] += 1;
      return acc;
    },
    [0, 0, 0, 0, 0]
  );

  const classChartData = {
    labels: ["Ẩm ướt", "Bình thường", "Hạn nhẹ", "Hạn nặng", "Hạn cực đoan"],
    datasets: [{ data: classCounts, backgroundColor: droughtColors }]
  };

  return (
    <>
      <SyncProgressModal
        open={syncing}
        title="Đang tải dữ liệu TVDI từ GEE"
        description="Hệ thống đang kết nối Google Earth Engine, xử lý LST, NDVI và tính toán TVDI trước khi đồng bộ."
      />
      <section className="card page-header">
        <h1>Phân tích TVDI</h1>
        <p>Đánh giá tình trạng hạn hán qua TVDI, LST và tỷ lệ diện tích khô hạn.</p>
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
        <StatCard label="TVDI trung bình" value={stats?.average ?? "--"} />
        <StatCard label="LST trung bình (°C)" value={stats?.avg_lst ?? "--"} />
        <StatCard label="Tỷ lệ hạn (%)" value={stats?.drought_pct ?? "--"} />
        <StatCard label="Ngày hạn nặng" value={stats?.drought_days ?? "--"} />
      </section>

      <section className="chart-grid">
        <div className="card chart-card">
          <h3>TVDI theo thời gian</h3>
          <Line data={tvdiLineData} />
        </div>
      </section>

      <section className="chart-grid two">
        <div className="card chart-card">
          <h3>TVDI trung bình theo tháng</h3>
          <Bar data={monthlyChartData} />
        </div>
        <div className="card chart-card">
          <h3>Phân loại hạn hán</h3>
          <Doughnut data={classChartData} />
        </div>
      </section>
    </>
  );
}
