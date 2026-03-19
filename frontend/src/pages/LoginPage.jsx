import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, isAuthenticated, ready } = useAuth();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(form.username.trim(), form.password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.response?.data?.error?.message || "Đăng nhập thất bại");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (ready && isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, navigate, ready]);

  return (
    <div className="auth-shell">
      <section className="card auth-card">
        <h1>Đăng nhập</h1>
        <p>Hệ thống phân tích và đánh giá biến đổi thời tiết</p>
        {error && <div className="status error">{error}</div>}
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="username">Tên đăng nhập</label>
            <input
              id="username"
              value={form.username}
              onChange={(e) => setForm((prev) => ({ ...prev, username: e.target.value }))}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Mật khẩu</label>
            <input
              id="password"
              type="password"
              value={form.password}
              onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
              required
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? "Đang xử lý..." : "Đăng nhập"}
          </button>
        </form>
        <p className="auth-link">
          Chưa có tài khoản? <Link to="/register">Đăng ký ngay</Link>
        </p>
      </section>
    </div>
  );
}
