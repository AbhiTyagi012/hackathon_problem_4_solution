import { createPortal } from "react-dom";

export interface ToastMessage {
  id: number;
  kind: "success" | "error";
  text: string;
}

export function ToastStack({ toasts, onDismiss }: { toasts: ToastMessage[]; onDismiss: (id: number) => void }) {
  if (toasts.length === 0) return null;

  return createPortal(
    <div
      style={{
        position: "fixed",
        top: 16,
        right: 16,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        zIndex: 2000,
      }}
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          onClick={() => onDismiss(t.id)}
          style={{
            minWidth: 240,
            maxWidth: 360,
            padding: "10px 14px",
            borderRadius: 10,
            fontSize: 13.5,
            cursor: "pointer",
            color: "#fff",
            background: t.kind === "success" ? "#16a34a" : "#dc2626",
            boxShadow: "0 8px 24px rgba(0, 0, 0, 0.25)",
          }}
        >
          {t.text}
        </div>
      ))}
    </div>,
    document.body
  );
}
