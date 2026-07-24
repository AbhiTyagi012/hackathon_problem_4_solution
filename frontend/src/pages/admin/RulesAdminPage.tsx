import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import type { Rule, RuleCreate, RulePreviewResponse } from "../../api/types";
import { ConditionTree } from "../../components/ConditionTree";
import { Modal } from "../../components/Modal";
import { RuleForm, type RuleFormInitial } from "../../components/RuleForm";
import { ToastStack, type ToastMessage } from "../../components/Toast";
import { logger } from "../../lib/logger";

export function RulesAdminPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [preview, setPreview] = useState<RulePreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [showForm, setShowForm] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [nlDraft, setNlDraft] = useState<RuleFormInitial | null>(null);

  const [nlText, setNlText] = useState("");
  const [nlLoading, setNlLoading] = useState(false);
  const [nlNote, setNlNote] = useState("");

  const [saveFeedback, setSaveFeedback] = useState<RulePreviewResponse | null>(null);

  const [reviewText, setReviewText] = useState("");
  const [reviewLoading, setReviewLoading] = useState(false);

  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const toastId = useRef(0);
  const pushToast = (kind: ToastMessage["kind"], text: string) => {
    const id = ++toastId.current;
    setToasts((prev) => [...prev, { id, kind, text }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  };

  const loadRules = () => {
    setLoading(true);
    api
      .listRules()
      .then(setRules)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(loadRules, []);

  const openPreview = async (id: string) => {
    setSelectedId(id);
    setPreviewLoading(true);
    try {
      setPreview(await api.previewRule(id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setPreviewLoading(false);
    }
  };

  const generateFromText = async () => {
    if (!nlText.trim()) return;
    setNlLoading(true);
    setError("");
    logger.info("generating rule draft from text", { text: nlText });
    try {
      const res = await api.ruleFromText(nlText);
      setNlDraft(res.rule);
      setNlNote(`${res.notes} (source: ${res.source})`);
      setEditingRule(null);
      setShowForm(true);
    } catch (e) {
      logger.error("rule generation failed", e);
      setError((e as Error).message);
    } finally {
      setNlLoading(false);
    }
  };

  const handleSave = async (payload: RuleCreate) => {
    setError("");
    const isEdit = Boolean(editingRule);
    try {
      const saved = editingRule
        ? await api.updateRule(editingRule.id, payload)
        : await api.createRule(payload);
      logger.info(`rule ${isEdit ? "updated" : "created"}`, { id: saved.id, name: saved.name });
      pushToast("success", isEdit ? `Rule "${saved.name}" updated` : `Rule "${saved.name}" added`);
      setShowForm(false);
      setEditingRule(null);
      setNlDraft(null);
      setNlText("");
      loadRules();
      const fb = await api.previewRule(saved.id);
      setSaveFeedback(fb);
      openPreview(saved.id);
    } catch (e) {
      logger.error(`rule ${isEdit ? "update" : "creation"} failed`, e);
      setError((e as Error).message);
      pushToast("error", `Failed to ${isEdit ? "update" : "add"} rule: ${(e as Error).message}`);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this rule?")) return;
    const rule = rules.find((r) => r.id === id);
    try {
      await api.deleteRule(id);
      logger.info("rule deleted", { id });
      pushToast("success", `Rule "${rule?.name ?? id}" deleted`);
      if (selectedId === id) {
        setSelectedId(null);
        setPreview(null);
      }
      loadRules();
    } catch (e) {
      logger.error("rule deletion failed", e);
      pushToast("error", `Failed to delete rule: ${(e as Error).message}`);
    }
  };

  const move = async (index: number, direction: -1 | 1) => {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= rules.length) return;
    const reordered = [...rules];
    [reordered[index], reordered[newIndex]] = [reordered[newIndex], reordered[index]];
    const ids = reordered.map((r) => r.id);
    setRules(reordered);
    try {
      setRules(await api.reorderRules(ids));
      logger.info("rules reordered", { ids });
    } catch (e) {
      logger.error("rule reorder failed", e);
      setError((e as Error).message);
      loadRules();
    }
  };

  const runReview = async () => {
    setReviewLoading(true);
    logger.info("running AI ruleset review");
    try {
      setReviewText((await api.reviewRules()).review);
    } catch (e) {
      logger.error("ruleset review failed", e);
      setError((e as Error).message);
    } finally {
      setReviewLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 16px", display: "flex", gap: 24 }}>
      <div style={{ flex: 2, minWidth: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>Rule Administration</h2>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={runReview} disabled={reviewLoading} style={secondaryButton}>
              {reviewLoading ? "Reviewing…" : "🔍 Review ruleset (AI)"}
            </button>
            <button
              onClick={() => {
                setShowForm(true);
                setEditingRule(null);
                setNlDraft(null);
              }}
              style={primaryButton}
            >
              + New rule
            </button>
          </div>
        </div>

        <div style={{ border: "1px solid var(--border)", borderRadius: 10, padding: 16, marginBottom: 16, background: "var(--surface)" }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>✨ Describe a rule in plain English</div>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              value={nlText}
              onChange={(e) => setNlText(e.target.value)}
              placeholder="e.g. Recommend gaming accessories to users interested in gaming who search for a laptop, priority high"
              style={{ flex: 1, padding: "8px 10px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--fg)" }}
            />
            <button onClick={generateFromText} disabled={nlLoading} style={primaryButton}>
              {nlLoading ? "Generating…" : "Generate"}
            </button>
          </div>
        </div>

        {error && <p style={{ color: "crimson" }}>{error}</p>}
        {reviewText && (
          <div style={{ ...panel, whiteSpace: "pre-wrap", marginBottom: 16 }}>
            <strong>AI ruleset review:</strong>
            <div>{reviewText}</div>
          </div>
        )}
        {saveFeedback && (
          <div style={{ ...panel, marginBottom: 16, borderColor: saveFeedback.needs_product ? "#f59e0b" : "#16a34a" }}>
            <strong>{saveFeedback.needs_product ? "⚠ Rule saved — no matching product yet" : "✓ Rule saved"}</strong>
            <div>{saveFeedback.feedback}</div>
          </div>
        )}

        {loading ? (
          <p>Loading rules…</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "2px solid var(--border)" }}>
                <th style={th}>Priority</th>
                <th style={th}>Name</th>
                <th style={th}>Condition</th>
                <th style={th}>Recommends</th>
                <th style={th}>v</th>
                <th style={th}></th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule, idx) => (
                <tr
                  key={rule.id}
                  onClick={() => openPreview(rule.id)}
                  style={{
                    borderBottom: "1px solid var(--border)",
                    cursor: "pointer",
                    background: selectedId === rule.id ? "var(--bg)" : "transparent",
                    opacity: rule.enabled ? 1 : 0.5,
                  }}
                >
                  <td style={td}>
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      {rule.priority}
                      <button style={miniButton} onClick={(e) => { e.stopPropagation(); move(idx, -1); }}>▲</button>
                      <button style={miniButton} onClick={(e) => { e.stopPropagation(); move(idx, 1); }}>▼</button>
                    </div>
                  </td>
                  <td style={td}>
                    <div style={{ fontWeight: 600 }}>{rule.name}</div>
                    <div style={{ color: "var(--fg-muted)" }}>{rule.description}</div>
                  </td>
                  <td style={td}>
                    <ConditionTree condition={rule.condition} />
                  </td>
                  <td style={td}>
                    {[...rule.recommend.categories, ...rule.recommend.tags].join(", ") || "—"} · score {rule.recommend.score}
                  </td>
                  <td style={td}>{rule.version}</td>
                  <td style={td} onClick={(e) => e.stopPropagation()}>
                    <button
                      style={miniButton}
                      onClick={() => {
                        setEditingRule(rule);
                        setNlDraft(null);
                        setShowForm(true);
                      }}
                    >
                      Edit
                    </button>
                    <button style={{ ...miniButton, color: "crimson" }} onClick={() => handleDelete(rule.id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {showForm && (
          <Modal
            title={editingRule ? `Edit: ${editingRule.name}` : "New rule"}
            onClose={() => {
              setShowForm(false);
              setEditingRule(null);
              setNlDraft(null);
            }}
          >
            {nlNote && !editingRule && <p style={{ fontSize: 12, color: "var(--fg-muted)" }}>{nlNote}</p>}
            <RuleForm
              initial={editingRule ?? nlDraft ?? undefined}
              submitLabel={editingRule ? "Save changes" : "Create rule"}
              onSubmit={handleSave}
              onCancel={() => {
                setShowForm(false);
                setEditingRule(null);
                setNlDraft(null);
              }}
            />
          </Modal>
        )}
      </div>

      <ToastStack toasts={toasts} onDismiss={(id) => setToasts((prev) => prev.filter((t) => t.id !== id))} />

      <div style={{ flex: 1, minWidth: 280 }}>
        <h3>Live preview</h3>
        {!selectedId && <p style={{ color: "var(--fg-muted)", fontSize: 13 }}>Select a rule to preview what it recommends.</p>}
        {previewLoading && <p>Loading preview…</p>}
        {preview && (
          <div style={panel}>
            <div style={{ fontSize: 13, marginBottom: 8 }}>
              Sample match: <strong>{preview.matched ? "✓ matches demo profile" : "✗ no match on demo profile"}</strong>
            </div>
            <div style={{ fontSize: 13, marginBottom: 10 }}>{preview.feedback}</div>
            {preview.matched_products.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {preview.matched_products.map((p) => (
                  <div key={p.id} style={{ fontSize: 13, borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>
                    <strong>{p.name}</strong> — ${p.price.toFixed(2)}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const th: React.CSSProperties = { padding: "8px 6px" };
const td: React.CSSProperties = { padding: "8px 6px", verticalAlign: "top" };
const panel: React.CSSProperties = {
  border: "1px solid var(--border)",
  borderRadius: 10,
  padding: 16,
  background: "var(--surface)",
};
const primaryButton: React.CSSProperties = {
  background: "var(--accent)",
  color: "#fff",
  border: "none",
  borderRadius: 8,
  padding: "8px 16px",
  fontWeight: 600,
  cursor: "pointer",
  whiteSpace: "nowrap",
};
const secondaryButton: React.CSSProperties = {
  background: "var(--bg)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: "8px 16px",
  cursor: "pointer",
  whiteSpace: "nowrap",
};
const miniButton: React.CSSProperties = {
  background: "var(--bg)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  padding: "2px 8px",
  cursor: "pointer",
  fontSize: 12,
  marginRight: 4,
};
