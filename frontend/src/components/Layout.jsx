import { LogOut } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

const links = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/map", label: "Bản đồ" },
  { to: "/rainfall", label: "Lượng mưa" },
  { to: "/temperature", label: "Nhiệt độ" },
  { to: "/soil-moisture", label: "Độ ẩm đất" },
  { to: "/ndvi", label: "NDVI" },
  { to: "/tvdi", label: "TVDI" },
  { to: "/activity", label: "Hoạt động" }
];

export default function Layout() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const onLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/" className="brand">
          GIS Climate Lab
        </NavLink>
        <nav className="nav-links">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="user-box">
          <span>{user?.fullName || user?.username}</span>
          <button type="button" className="btn btn-danger" onClick={onLogout}>
            <LogOut size={16} /> Đăng xuất
          </button>
        </div>
      </header>
      <main className="container">
        <Outlet />
      </main>
    </div>
  );
}
