import { NavLink } from "react-router-dom";

const linkStyle = ({ isActive }: { isActive: boolean }) => ({
  padding: "8px 14px",
  borderRadius: 8,
  textDecoration: "none",
  color: isActive ? "#fff" : "var(--fg-muted)",
  background: isActive ? "var(--accent)" : "transparent",
  fontWeight: 600,
  fontSize: 14,
});

export function NavBar() {
  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "12px 24px",
        borderBottom: "1px solid var(--border)",
        position: "sticky",
        top: 0,
        background: "var(--bg)",
        zIndex: 10,
      }}
    >
      <span style={{ fontWeight: 800, marginRight: 16, fontSize: 16 }}>🛍️ ShopSense</span>
      <NavLink to="/" style={linkStyle} end>
        Home
      </NavLink>
      <NavLink to="/search" style={linkStyle}>
        Search
      </NavLink>
      <NavLink to="/profile" style={linkStyle}>
        Profile
      </NavLink>
      <div style={{ flex: 1 }} />
      <NavLink to="/admin" style={linkStyle}>
        ⚙ Admin
      </NavLink>
    </nav>
  );
}
