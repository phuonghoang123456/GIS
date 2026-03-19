import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="auth-shell">
      <section className="card auth-card">
        <h1>Không tìm thấy trang</h1>
        <p>Đường dẫn bạn mở không tồn tại hoặc đã được thay đổi.</p>
        <Link className="btn btn-primary" to="/">
          Về trang chủ
        </Link>
      </section>
    </div>
  );
}
