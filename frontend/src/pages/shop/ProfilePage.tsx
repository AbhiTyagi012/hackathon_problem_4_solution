import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useProfile } from "../../context/ProfileContext";

export function ProfilePage() {
  const { profile, setProfile } = useProfile();
  const navigate = useNavigate();
  const [form, setForm] = useState(profile);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setProfile(form);
    navigate("/");
  };

  return (
    <div style={{ maxWidth: 560, margin: "32px auto", padding: "0 16px" }}>
      <h2>Your shopper profile</h2>
      <p style={{ color: "var(--fg-muted)", fontSize: 14 }}>
        Recommendations across Home, Search, and post-purchase are driven by this profile plus the
        configurable rules an admin manages in <code>/admin</code>.
      </p>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <label style={label}>
          Age
          <input
            type="number"
            value={form.age ?? ""}
            onChange={(e) => setForm({ ...form, age: e.target.value ? Number(e.target.value) : null })}
            style={input}
          />
        </label>

        <label style={label}>
          Gender
          <select
            value={form.gender ?? ""}
            onChange={(e) => setForm({ ...form, gender: e.target.value || null })}
            style={input}
          >
            <option value="">Prefer not to say</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="other">Other</option>
          </select>
        </label>

        <label style={label}>
          Budget band
          <select
            value={form.budget_band ?? ""}
            onChange={(e) => setForm({ ...form, budget_band: e.target.value || null })}
            style={input}
          >
            <option value="">—</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </label>

        <label style={label}>
          Max budget ($)
          <input
            type="number"
            value={form.max_budget ?? ""}
            onChange={(e) => setForm({ ...form, max_budget: e.target.value ? Number(e.target.value) : null })}
            style={input}
          />
        </label>

        <label style={label}>
          Location
          <input
            value={form.location ?? ""}
            onChange={(e) => setForm({ ...form, location: e.target.value || null })}
            style={input}
          />
        </label>

        <button type="submit" style={primaryButton}>
          Save profile &amp; see recommendations
        </button>
      </form>
    </div>
  );
}

const label: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 6, fontSize: 13 };
const input: React.CSSProperties = {
  padding: "8px 10px",
  borderRadius: 8,
  border: "1px solid var(--border)",
  background: "var(--surface)",
  color: "var(--fg)",
};
const primaryButton: React.CSSProperties = {
  background: "var(--accent)",
  color: "#fff",
  border: "none",
  borderRadius: 10,
  padding: "12px 20px",
  fontWeight: 700,
  cursor: "pointer",
  fontSize: 15,
};
