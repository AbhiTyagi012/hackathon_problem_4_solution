export function RecommendationExplanation({
  reason,
  matchedRuleIds,
}: {
  reason: string;
  matchedRuleIds: string[];
}) {
  return (
    <div
      style={{
        fontSize: 12.5,
        background: "var(--bg)",
        border: "1px dashed var(--border)",
        borderRadius: 8,
        padding: 10,
        color: "var(--fg-muted)",
      }}
    >
      <div>{reason}</div>
      {matchedRuleIds.length > 0 && (
        <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {matchedRuleIds.map((id) => (
            <span
              key={id}
              style={{
                background: "#dcfce7",
                color: "#166534",
                borderRadius: 999,
                padding: "2px 8px",
                fontWeight: 600,
              }}
            >
              {id}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function DecisionTraceList({
  matched,
  rejected,
}: {
  matched: { rule_id: string; rule_name: string; reason: string }[];
  rejected: { rule_id: string; rule_name: string; reason: string }[];
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13 }}>
      {matched.map((t) => (
        <div key={t.rule_id} style={{ ...traceRow, background: "#dcfce7", color: "#166534" }}>
          <strong>✓ {t.rule_name}</strong>
          <span style={{ opacity: 0.8 }}>{t.reason}</span>
        </div>
      ))}
      {rejected.map((t) => (
        <div key={t.rule_id} style={{ ...traceRow, background: "var(--bg)", color: "var(--fg-muted)" }}>
          <strong>✗ {t.rule_name}</strong>
          <span style={{ opacity: 0.8 }}>{t.reason}</span>
        </div>
      ))}
    </div>
  );
}

const traceRow: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 2,
  borderRadius: 8,
  padding: "8px 10px",
};
