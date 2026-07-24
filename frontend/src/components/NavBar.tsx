import { NavLink } from "react-router-dom";

export function NavBar() {
  return (
    <nav className="navbar">
      <NavLink to="/" className="navbar-brand" end>
        🛍️ ShopSense
      </NavLink>
      <NavLink to="/" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} end>
        Home
      </NavLink>
      <NavLink to="/search" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
        Search
      </NavLink>
      <NavLink to="/profile" className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
        Profile
      </NavLink>
      <div className="navbar-spacer" />
      <NavLink to="/admin" className={({ isActive }) => `nav-link nav-link-admin${isActive ? " active" : ""}`}>
        ⚙ Admin
      </NavLink>
    </nav>
  );
}
