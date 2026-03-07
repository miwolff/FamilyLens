import "./IndexProgress.css";

function formatTime(seconds) {
  if (seconds == null || seconds < 0) return null;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function IndexProgress({ progress, onCancel }) {
  if (!progress || progress.status === "idle") return null;

  const { status, current, total, indexed, skipped, errors, elapsed_seconds, eta_seconds, result } = progress;

  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  const elapsed = formatTime(elapsed_seconds);
  const eta = formatTime(eta_seconds);

  const isRunning = status === "running";
  const isCancelling = status === "cancelling";
  const isComplete = status === "complete";
  const isCancelled = status === "cancelled";
  const isError = status === "error";

  const statusLabel = isRunning
    ? "Indexing photos…"
    : isCancelling
    ? "Cancelling…"
    : isComplete
    ? "Indexing complete"
    : isCancelled
    ? "Indexing cancelled"
    : "Indexing failed";

  return (
    <div className={`index-progress index-progress--${status}`}>
      <div className="index-progress-header">
        <span className="index-progress-title">{statusLabel}</span>

        {(isRunning || isCancelling) && (
          <button
            className="btn btn-cancel"
            onClick={onCancel}
            disabled={isCancelling}
          >
            {isCancelling ? "Cancelling…" : "Cancel"}
          </button>
        )}
      </div>

      {total > 0 && (
        <>
          <div className="index-progress-bar-wrapper">
            <div
              className="index-progress-bar-fill"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="index-progress-timing">
            <span>{current} / {total} files — {pct}%</span>
            <span className="index-progress-time">
              {elapsed && `Elapsed: ${elapsed}`}
              {eta && isRunning && ` · ~${eta} remaining`}
            </span>
          </div>
        </>
      )}

      {total === 0 && (isRunning || isCancelling) && (
        <div className="index-progress-timing">
          <span>Discovering files…</span>
        </div>
      )}

      <div className="index-progress-counts">
        <span>{indexed} indexed</span>
        <span>{skipped} skipped</span>
        {errors > 0 && (
          <span className="index-progress-errors">{errors} errors</span>
        )}
        {isComplete && result && (
          <span className="index-progress-total">
            {result.total_in_collection} total in library
          </span>
        )}
      </div>
    </div>
  );
}

export default IndexProgress;
