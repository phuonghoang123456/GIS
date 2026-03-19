import { LogOut } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

const links = [
  { to: "/", label: "Trang chủ", end: true },
  { to: "/rainfall", label: "Lượng mưa" },
  { to: "/temperature", label: "Nhiệt độ" },
  { to: "/ndvi", label: "NDVI" },
  { to: "/tvdi", label: "TVDI" }
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
