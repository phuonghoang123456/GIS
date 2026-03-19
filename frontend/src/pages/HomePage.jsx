import { Link } from "react-router-dom";
import { useEffect } from "react";

import { useAuth } from "../context/AuthContext";

const cards = [
  {
    to: "/rainfall",
    title: "Phân tích lượng mưa",
    description: "Theo dõi CHIRPS, thống kê ngày/tháng/năm và so sánh 2 giai đoạn."
  },
  {
    to: "/temperature",
    title: "Phân tích nhiệt độ",
    description: "Đánh giá xu hướng nhiệt độ và biên độ dao động theo thời gian."
  },
  {
    to: "/ndvi",
    title: "Phân tích NDVI",
    description: "Giám sát sức khỏe thảm thực vật, phân loại độ che phủ."
  },
  {
    to: "/tvdi",
    title: "Phân tích TVDI",
    description: "Đánh giá tình trạng hạn hán và cảnh báo sớm theo ngưỡng."
  }
];

export default function HomePage() {
  const { logActivity } = useAuth();

  useEffect(() => {
    void logActivity("page_view", "home");
  }, [logActivity]);

  return (
    <>
      <section className="card page-header">
        <h1>Hệ thống Phân tích và Đánh giá Biến đổi Thời tiết</h1>
        <p>
          Nền tảng Web GIS mới được refactor với Django REST + React Vite, giữ đầy đủ chức năng
          quản trị dữ liệu khí hậu.
        </p>
      </section>
      <section className="chart-grid two">
        {cards.map((card) => (
          <Link key={card.to} to={card.to} className="card chart-card" style={{ textDecoration: "none" }}>
            <h3>{card.title}</h3>
            <p style={{ color: "var(--muted)", margin: 0 }}>{card.description}</p>
          </Link>
        ))}
      </section>
    </>
  );
}
