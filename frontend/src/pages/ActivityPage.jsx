import { useEffect, useMemo, useState } from "react";

import { apiClient, authHeaders } from "../api/client";
import StatCard from "../components/StatCard";
import { useAuth } from "../context/AuthContext";

function formatDateTime(value) {
  if (!value) {
    return "--";
  }
  try {
    return new Date(value).toLocaleString("vi-VN");
  } catch {
    return value;
  }
}

export default function ActivityPage() {
  const { token, logActivity } = useAuth();
  const [form, setForm] = useState({
    startDate: "2020-01-01",
    endDate: new Date().toISOString().slice(0, 10)
  });
  const [status, setStatus] = useState("");
  const [statusType, setStatusType] = useState("ok");
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState([]);
  const [recentActivities, setRecentActivities] = useState([]);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    void logActivity("page_view", "activity");
  }, [logActivity]);

  const loadActivity = async () => {
    if (!token) {
      return;
    }
    setLoading(true);
    setStatus("");
    try {
      const [statsResponse, historyResponse] = await Promise.all([
        apiClient.get("/activity/stats", {
          params: {
            startDate: `${form.startDate}T00:00:00Z`,
            endDate: `${form.endDate}T23:59:59Z`
          },
          headers: authHeaders(token)
        }),
        apiClient.get("/activity/history", {
          params: { limit: 50, offset: 0 },
          headers: authHeaders(token)
        })
      ]);

      setStats(statsResponse.data?.data?.stats || []);
      setRecentActivities(statsResponse.data?.data?.recentActivities || []);
      setHistory(historyResponse.data?.data?.activities || []);
      setStatus("Đã tải lịch sử và thống kê hoạt động.");
      setStatusType("ok");
    } catch (err) {
      setStatus(err.response?.data?.error?.message || "Không tải được dữ liệu hoạt động.");
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadActivity();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const summary = useMemo(() => {
    const total = stats.reduce((sum, item) => sum + Number(item.count || 0), 0);
    const top = stats[0];
    return {
      total,
      distinct: stats.length,
      topType: top?.activity_type || "--",
      topCount: top?.count || 0
    };
  }, [stats]);

  return (
    <div className="panel-stack">
      <section className="card page-header">
        <h1>Lịch sử hoạt động người dùng</h1>
        <p>Theo dõi các thao tác gần đây, thống kê hành vi sử dụng và những tương tác mới nhất trong hệ thống.</p>
      </section>

      {status && <div className={`status ${statusType}`}>{status}</div>}

      <section className="card controls">
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
          <button type="button" className="btn btn-primary" onClick={loadActivity} disabled={loading}>
            {loading ? "Đang tải..." : "Làm mới lịch sử"}
          </button>
        </div>
      </section>

      <section className="grid-4">
        <StatCard label="Tổng hoạt động" value={summary.total} />
        <StatCard label="Loại hoạt động" value={summary.distinct} />
        <StatCard label="Hoạt động nhiều nhất" value={summary.topType} />
        <StatCard label="Số lần của hoạt động top" value={summary.topCount} />
      </section>

      <section className="split-grid">
        <div className="card table-card">
          <h3>Thống kê theo loại hoạt động</h3>
          {stats.length === 0 ? (
            <p className="empty-note">Chưa có thống kê hoạt động trong khoảng thời gian đã chọn.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Loại hoạt động</th>
                  <th>Số lần</th>
                  <th>Lần đầu</th>
                  <th>Gần nhất</th>
                </tr>
              </thead>
              <tbody>
                {stats.map((item) => (
                  <tr key={item.activity_type}>
                    <td>{item.activity_type}</td>
                    <td>{item.count}</td>
                    <td>{formatDateTime(item.first_activity)}</td>
                    <td>{formatDateTime(item.last_activity)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card table-card">
          <h3>Hoạt động gần đây</h3>
          {recentActivities.length === 0 ? (
            <p className="empty-note">Chưa có hoạt động gần đây.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Loại</th>
                  <th>Trang</th>
                  <th>Chi tiết</th>
                  <th>Thời gian</th>
                </tr>
              </thead>
              <tbody>
                {recentActivities.map((item, index) => (
                  <tr key={`${item.activity_type}-${item.created_at}-${index}`}>
                    <td>{item.activity_type}</td>
                    <td>{item.page}</td>
                    <td>{Object.keys(item.details || {}).length > 0 ? JSON.stringify(item.details) : "--"}</td>
                    <td>{formatDateTime(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section className="card table-card">
        <h3>Lịch sử đầy đủ gần nhất</h3>
        {history.length === 0 ? (
          <p className="empty-note">Chưa có bản ghi lịch sử.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Loại hoạt động</th>
                <th>Trang</th>
                <th>Chi tiết</th>
                <th>Thời gian</th>
              </tr>
            </thead>
            <tbody>
              {history.map((item) => (
                <tr key={item.id}>
                  <td>{item.id}</td>
                  <td>{item.activity_type}</td>
                  <td>{item.page}</td>
                  <td>{Object.keys(item.details || {}).length > 0 ? JSON.stringify(item.details) : "--"}</td>
                  <td>{formatDateTime(item.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
