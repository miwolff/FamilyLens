import PropTypes from "prop-types";
import "./IndexProgress.css";

function formatTime(seconds) {
  if (seconds == null || seconds < 0) return null;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function IndexProgress({ progress, onCancel }) {
  if (!progress || progress.status === "idle") return null;

  const {
    status,
    stage,
    current,
    total,
    skipped,
    errors,
    removed,
    elapsed_seconds,
    eta_seconds,
    cluster_error,
    result,
  } = progress;

  const pct = total > 0 ? Math.round((current / total) * 100) : stage === "clustering" ? 100 : 0;
  const elapsed = formatTime(elapsed_seconds);
  const eta = formatTime(eta_seconds);

  const isRunning = status === "running";
  const isCancelling = status === "cancelling";
  const isComplete = status === "complete";
  const isCancelled = status === "cancelled";
  const isError = status === "error";

  const statusLabel = isRunning
    ? stage === "clustering"
      ? "Building clusters…"
      : null
    : isCancelling
    ? "Cancelling…"
    : isComplete
    ? "Indexing complete"
    : isCancelled
    ? "Indexing cancelled"
    : "Indexing failed";

  const summary = [];
  if (total > 0 && (isRunning || isCancelling)) {
    summary.push(`${current}/${total}`);
    summary.push(`${pct}%`);
  } else if (stage === "clustering" && (isRunning || isCancelling)) {
    summary.push("100%");
  }

  if (elapsed) {
    summary.push(elapsed);
  }
  if (eta && isRunning) {
    summary.push(`${eta} left`);
  }
  if (isComplete && result) {
    summary.push(`${result.total_in_collection} total`);
  }

  const metrics = [];
  if (skipped > 0 || isComplete) {
    metrics.push(`${skipped} skipped`);
  }
  if (removed > 0) {
    metrics.push(`${removed} removed`);
  }
  if (errors > 0 || isError) {
    metrics.push(`${errors} errors`);
  }
  if ((isRunning || isCancelling) && total === 0) {
    metrics.push("Discovering files");
  }
  if (stage === "clustering") {
    metrics.push("Updating clusters");
  }
  if (cluster_error) {
    metrics.push("Clusters unavailable");
  }

  return (
    <div className={`index-progress index-progress--${status}`}>
      <div className="index-progress-main">
        {statusLabel && (
          <span className="index-progress-title">{statusLabel}</span>
        )}
        {summary.length > 0 && (
          <span className="index-progress-summary">{summary.join(" · ")}</span>
        )}
      </div>

      {metrics.length > 0 && (
        <div className="index-progress-counts">
          {metrics.map((metric) => (
            <span key={metric}>{metric}</span>
          ))}
        </div>
      )}

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
  );
}

export default IndexProgress;

IndexProgress.propTypes = {
  progress: PropTypes.shape({
    status: PropTypes.string.isRequired,
    stage: PropTypes.string,
    current: PropTypes.number,
    total: PropTypes.number,
    indexed: PropTypes.number,
    skipped: PropTypes.number,
    errors: PropTypes.number,
    removed: PropTypes.number,
    elapsed_seconds: PropTypes.number,
    eta_seconds: PropTypes.number,
    cluster_error: PropTypes.string,
    result: PropTypes.shape({
      total_in_collection: PropTypes.number,
      total_clusters: PropTypes.number,
    }),
  }).isRequired,
  onCancel: PropTypes.func.isRequired,
};
