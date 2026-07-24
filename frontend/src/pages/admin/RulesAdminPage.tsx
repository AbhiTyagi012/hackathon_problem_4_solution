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
  const [draftPreview, setDraftPreview] = useState<RulePreviewResponse | null>(null);

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
    setDraftPreview(null);
    logger.info("generating rule draft from text", { text: nlText });
    try {
      const res = await api.ruleFromText(nlText);
      setNlDraft(res.rule);
      setNlNote(`${res.notes} (source: ${res.source})`);
      setEditingRule(null);
      setShowForm(true);
      try {
        setDraftPreview(await api.previewDraftRule(res.rule));
      } catch (previewErr) {
        logger.error("draft preview failed", previewErr);
      }
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
      setDraftPreview(null);
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

  const enabledCount = rules.filter((r) => r.enabled).length;

  return (
    <div className="admin-page">
      <div className="admin-main">
        <div className="admin-header">
          <div>
            <h2>Rule Administration</h2>
            <p className="section-subtitle">Configure recommendation logic without code changes</p>
          </div>
          <div className="admin-actions">
            <button onClick={runReview} disabled={reviewLoading} className="btn-secondary">
              {reviewLoading ? "Reviewing…" : "Review ruleset (AI)"}
            </button>
            <button
              onClick={() => {
                setShowForm(true);
                setEditingRule(null);
                setNlDraft(null);
                setDraftPreview(null);
              }}
              className="btn-primary"
            >
              + New rule
            </button>
          </div>
        </div>

        <div className="admin-stat-row">
          <div className="admin-stat">
            <div className="admin-stat-value">{rules.length}</div>
            <div className="admin-stat-label">Total rules</div>
          </div>
          <div className="admin-stat">
            <div className="admin-stat-value">{enabledCount}</div>
            <div className="admin-stat-label">Enabled</div>
          </div>
          <div className="admin-stat">
            <div className="admin-stat-value">{rules.length - enabledCount}</div>
            <div className="admin-stat-label">Disabled</div>
          </div>
        </div>

        <div className="admin-panel admin-ai-panel">
          <div className="admin-panel-title">Describe a rule in plain English</div>
          <div className="admin-ai-row">
            <input
              value={nlText}
              onChange={(e) => setNlText(e.target.value)}
              placeholder="e.g. Recommend gaming accessories to users interested in gaming who search for a laptop, priority high"
              className="admin-ai-input"
            />
            <button onClick={generateFromText} disabled={nlLoading} className="btn-primary">
              {nlLoading ? "Generating…" : "Generate"}
            </button>
          </div>
        </div>

        {error && <p className="page-error">{error}</p>}
        {reviewText && (
          <div className="admin-alert">
            <strong>AI ruleset review</strong>
            <div style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>{reviewText}</div>
          </div>
        )}
        {saveFeedback && (
          <div className={`admin-alert ${saveFeedback.needs_product ? "warning" : "success"}`}>
            <strong>{saveFeedback.needs_product ? "Rule saved — no matching product yet" : "Rule saved successfully"}</strong>
            <div style={{ marginTop: 6 }}>{saveFeedback.feedback}</div>
          </div>
        )}

        {loading ? (
          <p className="page-status">Loading rules…</p>
        ) : (
          <div className="admin-rules-table-wrap">
            <table className="admin-rules-table">
              <thead>
                <tr>
                  <th>Priority</th>
                  <th>Name</th>
                  <th>Condition</th>
                  <th>Recommends</th>
                  <th>v</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule, idx) => (
                  <tr
                    key={rule.id}
                    onClick={() => openPreview(rule.id)}
                    className={`${selectedId === rule.id ? "selected" : ""}${rule.enabled ? "" : " disabled"}`}
                  >
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <strong>{rule.priority}</strong>
                        <button type="button" className="btn-ghost" onClick={(e) => { e.stopPropagation(); move(idx, -1); }}>▲</button>
                        <button type="button" className="btn-ghost" onClick={(e) => { e.stopPropagation(); move(idx, 1); }}>▼</button>
                      </div>
                    </td>
                    <td>
                      <div style={{ fontWeight: 700 }}>{rule.name}</div>
                      <div style={{ color: "var(--fg-muted)", marginTop: 4 }}>{rule.description}</div>
                    </td>
                    <td>
                      <ConditionTree condition={rule.condition} />
                    </td>
                    <td>
                      {[...rule.recommend.categories, ...rule.recommend.tags].join(", ") || "—"} · score {rule.recommend.score}
                    </td>
                    <td>{rule.version}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="btn-ghost"
                        onClick={() => {
                          setEditingRule(rule);
                          setNlDraft(null);
                          setDraftPreview(null);
                          setShowForm(true);
                        }}
                      >
                        Edit
                      </button>
                      <button type="button" className="btn-ghost btn-danger" onClick={() => handleDelete(rule.id)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {showForm && (
          <Modal
            title={editingRule ? `Edit: ${editingRule.name}` : "New rule"}
            onClose={() => {
              setShowForm(false);
              setEditingRule(null);
              setNlDraft(null);
              setDraftPreview(null);
            }}
          >
            {nlNote && !editingRule && <p style={{ fontSize: 12, color: "var(--fg-muted)" }}>{nlNote}</p>}
            {draftPreview && !editingRule && (
              <div className={`admin-alert ${draftPreview.needs_product ? "warning" : "success"}`} style={{ marginBottom: 12 }}>
                <strong>{draftPreview.needs_product ? "No matching product yet" : "Live match preview"}</strong>
                <div style={{ fontSize: 13, marginTop: 4 }}>{draftPreview.feedback}</div>
              </div>
            )}
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

      <aside className="admin-sidebar">
        <div className="admin-panel">
          <div className="admin-panel-title">Live preview</div>
          {!selectedId && (
            <p style={{ color: "var(--fg-muted)", fontSize: 13, margin: 0 }}>
              Select a rule to preview what it recommends against the demo profile.
            </p>
          )}
          {previewLoading && <p className="page-status">Loading preview…</p>}
          {preview && (
            <div className="admin-preview-card">
              <div style={{ fontSize: 13, marginBottom: 8 }}>
                Sample match: <strong>{preview.matched ? "matches demo profile" : "no match on demo profile"}</strong>
              </div>
              <div style={{ fontSize: 13, marginBottom: 10 }}>{preview.feedback}</div>
              {preview.matched_products.length > 0 && (
                <div>
                  {preview.matched_products.map((p) => (
                    <div key={p.id} className="admin-preview-product">
                      <strong>{p.name}</strong> — ${p.price.toFixed(2)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
