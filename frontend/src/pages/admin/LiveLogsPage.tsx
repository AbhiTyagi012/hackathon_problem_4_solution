import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import type { LogEntry } from "../../api/types";
import { logger } from "../../lib/logger";

const LEVELS = ["ALL", "INFO", "WARNING", "ERROR"] as const;
const MAX_SHOWN = 500;

export function LiveLogsPage() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [levelFilter, setLevelFilter] = useState<(typeof LEVELS)[number]>("ALL");
  const [search, setSearch] = useState("");

  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    let es: EventSource | null = null;

    (async () => {
      try {
        const initial = await api.recentLogs(200);
        if (cancelled) return;
        setEntries(initial);
        const lastSeq = initial.length ? initial[initial.length - 1].seq : 0;
        es = new EventSource(api.logsStreamUrl(lastSeq));
        es.onopen = () => setConnected(true);
        es.onerror = () => setConnected(false);
        es.onmessage = (ev) => {
          const entry: LogEntry = JSON.parse(ev.data);
          setEntries((prev) => {
            const next = [...prev, entry];
            return next.length > MAX_SHOWN ? next.slice(next.length - MAX_SHOWN) : next;
          });
        };
      } catch (e) {
        logger.error("failed to load logs", e);
      }
    })();

    return () => {
      cancelled = true;
      es?.close();
    };
  }, []);

  useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView({ block: "end" });
  }, [entries, autoScroll]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(nearBottom);
  };

  const filtered = entries.filter((e) => {
    if (levelFilter !== "ALL" && e.level !== levelFilter) return false;
    if (search) {
      const needle = search.toLowerCase();
      if (!e.message.toLowerCase().includes(needle) && !e.logger.toLowerCase().includes(needle)) {
        return false;
      }
    }
    return true;
  });

  return (
    <div className="admin-page">
      <div className="admin-main">
        <div className="admin-header">
          <div>
            <h2>Live Logs</h2>
            <p className="section-subtitle">
              Tails every log line the backend emits — request timing, rule CRUD, and each step of
              the rule-authoring pipeline (Interpret → Retrieve → Conflict-check → Validate → Preview)
              as it actually runs.
            </p>
          </div>
          <div className="admin-actions">
            <span className={`log-status ${connected ? "log-status-live" : "log-status-down"}`}>
              {connected ? "● Live" : "○ Connecting…"}
            </span>
          </div>
        </div>

        <div className="admin-panel log-controls">
          <div className="log-filter-row">
            {LEVELS.map((lvl) => (
              <button
                key={lvl}
                onClick={() => setLevelFilter(lvl)}
                className={`btn-ghost log-level-filter${levelFilter === lvl ? " active" : ""}`}
              >
                {lvl}
              </button>
            ))}
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter by message or logger name…"
              className="admin-ai-input log-search"
            />
            {!autoScroll && (
              <button className="btn-secondary" onClick={() => setAutoScroll(true)}>
                Resume auto-scroll
              </button>
            )}
          </div>
        </div>

        <div className="admin-panel log-console" ref={scrollRef} onScroll={handleScroll}>
          {filtered.length === 0 && <p className="page-status">No log entries yet.</p>}
          {filtered.map((e) => (
            <div key={e.seq} className={`log-line log-level-${e.level.toLowerCase()}`}>
              <span className="log-time">{e.timestamp.slice(11, 23)}</span>
              <span className="log-level-badge">{e.level}</span>
              <span className="log-logger">{e.logger}</span>
              <span className="log-message">{e.message}</span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
