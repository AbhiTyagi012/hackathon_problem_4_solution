import { useState } from "react";
import type { Condition, RuleCreate } from "../api/types";

const OPERATORS = [
  "eq", "ne", "gt", "gte", "lt", "lte", "between",
  "is_true", "is_false",
  "contains", "equals_ci", "starts_with", "regex",
  "in", "not_in", "any_in", "all_in",
  "exists", "date_before", "date_after",
];

const FIELD_SUGGESTIONS = [
  "age", "gender", "interests", "budget_band", "max_budget", "location",
  "past_purchase_categories", "context_type", "search_query", "search_category",
  "purchased_category", "purchased_tags",
];

interface LeafDraft {
  field: string;
  operator: string;
  value: string;
}

type Mode = "single" | "all" | "any";

function parseValue(raw: string): unknown {
  const trimmed = raw.trim();
  if (trimmed === "") return "";
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
}

function toLeafCondition(leaf: LeafDraft): Condition {
  return { field: leaf.field, operator: leaf.operator, value: parseValue(leaf.value) };
}

function draftFromCondition(condition?: Condition): { mode: Mode; leaves: LeafDraft[] } {
  if (!condition) return { mode: "single", leaves: [{ field: "", operator: "eq", value: "" }] };
  const toDraft = (c: Condition): LeafDraft => ({
    field: c.field ?? "",
    operator: c.operator ?? "eq",
    value: c.value === undefined ? "" : JSON.stringify(c.value),
  });
  if (condition.all) return { mode: "all", leaves: condition.all.map(toDraft) };
  if (condition.any) return { mode: "any", leaves: condition.any.map(toDraft) };
  return { mode: "single", leaves: [toDraft(condition)] };
}

export interface RuleFormInitial extends Partial<RuleCreate> {}

export function RuleForm({
  initial,
  onSubmit,
  onCancel,
  submitLabel = "Save rule",
}: {
  initial?: RuleFormInitial;
  onSubmit: (payload: RuleCreate) => void;
  onCancel?: () => void;
  submitLabel?: string;
}) {
  const initialDraft = draftFromCondition(initial?.condition);
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [priority, setPriority] = useState(initial?.priority ?? 50);
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [mode, setMode] = useState<Mode>(initialDraft.mode);
  const [leaves, setLeaves] = useState<LeafDraft[]>(initialDraft.leaves);
  const [products, setProducts] = useState((initial?.recommend?.products ?? []).join(", "));
  const [categories, setCategories] = useState((initial?.recommend?.categories ?? []).join(", "));
  const [tags, setTags] = useState((initial?.recommend?.tags ?? []).join(", "));
  const [score, setScore] = useState(initial?.recommend?.score ?? 2);

  const updateLeaf = (idx: number, patch: Partial<LeafDraft>) =>
    setLeaves((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));

  const addLeaf = () => setLeaves((prev) => [...prev, { field: "", operator: "eq", value: "" }]);
  const removeLeaf = (idx: number) => setLeaves((prev) => prev.filter((_, i) => i !== idx));

  const buildCondition = (): Condition => {
    if (mode === "single") return toLeafCondition(leaves[0]);
    if (mode === "all") return { all: leaves.map(toLeafCondition) };
    return { any: leaves.map(toLeafCondition) };
  };

  const splitCsv = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: RuleCreate = {
      name,
      description,
      enabled,
      priority: Number(priority),
      condition: buildCondition(),
      recommend: {
        products: splitCsv(products),
        categories: splitCsv(categories),
        tags: splitCsv(tags),
        score: Number(score),
      },
    };
    onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={row}>
        <label style={label}>
          Name
          <input value={name} onChange={(e) => setName(e.target.value)} required style={input} />
        </label>
        <label style={{ ...label, width: 100 }}>
          Priority
          <input
            type="number"
            value={priority}
            onChange={(e) => setPriority(Number(e.target.value))}
            style={input}
          />
        </label>
        <label style={{ ...label, width: 90, flexDirection: "row", alignItems: "center", gap: 6 }}>
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Enabled
        </label>
      </div>

      <label style={label}>
        Description
        <input value={description} onChange={(e) => setDescription(e.target.value)} style={input} />
      </label>

      <fieldset style={fieldset}>
        <legend>Condition</legend>
        <div style={{ display: "flex", gap: 12, marginBottom: 8 }}>
          {(["single", "all", "any"] as Mode[]).map((m) => (
            <label key={m} style={{ fontSize: 13 }}>
              <input type="radio" checked={mode === m} onChange={() => setMode(m)} /> {m.toUpperCase()}
            </label>
          ))}
        </div>
        {leaves.map((leaf, idx) => (
          <div key={idx} style={{ display: "flex", gap: 6, marginBottom: 6, alignItems: "center" }}>
            <input
              list="field-suggestions"
              placeholder="field"
              value={leaf.field}
              onChange={(e) => updateLeaf(idx, { field: e.target.value })}
              style={{ ...input, width: 160 }}
            />
            <select
              value={leaf.operator}
              onChange={(e) => updateLeaf(idx, { operator: e.target.value })}
              style={{ ...input, width: 120 }}
            >
              {OPERATORS.map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </select>
            <input
              placeholder='value (e.g. "gaming" or ["a","b"])'
              value={leaf.value}
              onChange={(e) => updateLeaf(idx, { value: e.target.value })}
              style={{ ...input, flex: 1 }}
            />
            {mode !== "single" && leaves.length > 1 && (
              <button type="button" onClick={() => removeLeaf(idx)} style={smallButton}>
                ✕
              </button>
            )}
          </div>
        ))}
        <datalist id="field-suggestions">
          {FIELD_SUGGESTIONS.map((f) => (
            <option key={f} value={f} />
          ))}
        </datalist>
        {mode !== "single" && (
          <button type="button" onClick={addLeaf} style={smallButton}>
            + condition
          </button>
        )}
      </fieldset>

      <fieldset style={fieldset}>
        <legend>Recommend</legend>
        <label style={label}>
          Product IDs (comma separated)
          <input value={products} onChange={(e) => setProducts(e.target.value)} style={input} />
        </label>
        <label style={label}>
          Categories (comma separated)
          <input value={categories} onChange={(e) => setCategories(e.target.value)} style={input} />
        </label>
        <label style={label}>
          Tags (comma separated)
          <input value={tags} onChange={(e) => setTags(e.target.value)} style={input} />
        </label>
        <label style={{ ...label, width: 120 }}>
          Score
          <input type="number" step="0.5" value={score} onChange={(e) => setScore(Number(e.target.value))} style={input} />
        </label>
      </fieldset>

      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" style={primaryButton}>
          {submitLabel}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} style={smallButton}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

const row: React.CSSProperties = { display: "flex", gap: 12 };
const label: React.CSSProperties = { display: "flex", flexDirection: "column", fontSize: 13, gap: 4, flex: 1 };
const input: React.CSSProperties = {
  padding: "6px 8px",
  borderRadius: 6,
  border: "1px solid var(--border)",
  background: "var(--bg)",
  color: "var(--fg)",
  fontSize: 13,
};
const fieldset: React.CSSProperties = {
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: 12,
};
const primaryButton: React.CSSProperties = {
  background: "var(--accent)",
  color: "#fff",
  border: "none",
  borderRadius: 8,
  padding: "8px 16px",
  fontWeight: 600,
  cursor: "pointer",
};
const smallButton: React.CSSProperties = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  padding: "4px 10px",
  cursor: "pointer",
  fontSize: 13,
};
