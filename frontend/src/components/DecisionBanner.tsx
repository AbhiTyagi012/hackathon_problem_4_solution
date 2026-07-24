import { useState } from "react";
import type { Decision } from "../api/types";
import { DecisionTraceList } from "./RecommendationExplanation";

export function DecisionBanner({ decision }: { decision: Decision }) {
  const [open, setOpen] = useState(false);

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "12px 16px",
        background: decision.used_ai_fallback ? "#f5f3ff" : "var(--surface)",
        fontSize: 13.5,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        <div>
          {decision.used_ai_fallback && <strong style={{ color: "#7c3aed" }}>AI fallback · </strong>}
          {decision.explanation}
        </div>
        <button
          onClick={() => setOpen((o) => !o)}
          style={{ border: "none", background: "none", color: "var(--accent)", cursor: "pointer", fontSize: 13, whiteSpace: "nowrap" }}
        >
          {open ? "Hide rule trace" : "Show rule trace"}
        </button>
      </div>
      {open && (
        <div style={{ marginTop: 10 }}>
          <DecisionTraceList matched={decision.rules_matched} rejected={decision.rules_rejected} />
        </div>
      )}
    </div>
  );
}
