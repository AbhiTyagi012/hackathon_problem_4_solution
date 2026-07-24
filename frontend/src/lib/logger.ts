/** Lightweight console logger so the app's key flows (API calls, admin rule
 * actions, recommendation fetches) leave a visible, timestamped trail — the
 * frontend counterpart to the backend's structured logging. */

type Level = "info" | "warn" | "error";

function emit(level: Level, message: string, data?: unknown) {
  const line = `${new Date().toISOString()} | ${level.toUpperCase().padEnd(5)} | ${message}`;
  const fn = level === "error" ? console.error : level === "warn" ? console.warn : console.info;
  if (data !== undefined) fn(line, data);
  else fn(line);
}

export const logger = {
  info: (message: string, data?: unknown) => emit("info", message, data),
  warn: (message: string, data?: unknown) => emit("warn", message, data),
  error: (message: string, data?: unknown) => emit("error", message, data),
};
