import { useState } from "react";
import type { Decision } from "../api/types";
import { DecisionTraceList } from "./RecommendationExplanation";

export function DecisionBanner({ decision }: { decision: Decision }) {
  const [open, setOpen] = useState(false);

  return (
    <div className={`decision-banner${decision.used_ai_fallback ? " ai" : ""}`}>
      <div className="decision-banner-row">
        <div>
          {decision.used_ai_fallback && <strong style={{ color: "#7c3aed" }}>AI fallback · </strong>}
          {decision.explanation}
        </div>
        <button type="button" onClick={() => setOpen((o) => !o)} className="link-button">
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
