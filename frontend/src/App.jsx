import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import IndexProgress from "./components/IndexProgress";
import { ApiError, requestJson } from "./lib/api";
import ClustersPage from "./pages/ClustersPage";
import SearchPage from "./pages/SearchPage";
import "./App.css";

const DEFAULT_POLL_DELAY_MS = 1000;
const HIDDEN_POLL_DELAY_MS = 4000;
const MAX_POLL_DELAY_MS = 8000;

function App() {
  const [progress, setProgress] = useState({ status: "idle", stage: "idle" });
  const [cleanup, setCleanup] = useState(false);
  // Cluster count default and limit come from the backend settings.
  const [clusterCount, setClusterCount] = useState("");
  const [maxClusterCount, setMaxClusterCount] = useState(null);
  const [indexMessage, setIndexMessage] = useState("");
  const [clusterCatalogVersion, setClusterCatalogVersion] = useState(0);
  const pollingRef = useRef(null);
  const pollFailureCountRef = useRef(0);
  const previousProgressStatusRef = useRef("idle");
  const progressStatusRef = useRef("idle");

  const syncClusterCount = (nextClusterCount) => {
    if (Number.isInteger(nextClusterCount) && nextClusterCount > 0) {
      setClusterCount(String(nextClusterCount));
    }
  };

  const stopPolling = () => {
    if (pollingRef.current) {
      window.clearTimeout(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const getNextPollDelay = () => {
    const baseDelay =
      document.visibilityState === "hidden"
        ? HIDDEN_POLL_DELAY_MS
        : DEFAULT_POLL_DELAY_MS;
    return Math.min(
      baseDelay * 2 ** Math.min(pollFailureCountRef.current, 2),
      MAX_POLL_DELAY_MS
    );
  };

  const fetchStatus = async ({ showError = false } = {}) => {
    try {
      const data = await requestJson("/api/index/status", {}, {
        defaultMessage: "Unable to load indexing status.",
        timeoutMessage: "Index status request timed out.",
      });

      pollFailureCountRef.current = 0;
      setProgress(data);
      progressStatusRef.current = data.status;
      syncClusterCount(data.cluster_count);
      if (data.status !== "idle") {
        setIndexMessage("");
      }
      if (["complete", "error", "cancelled"].includes(data.status)) {
        stopPolling();
      }
      return data;
    } catch (error) {
      pollFailureCountRef.current += 1;
      if (
        showError &&
        ["running", "cancelling"].includes(progressStatusRef.current)
      ) {
        setIndexMessage(
          error instanceof ApiError
            ? `Status updates paused: ${error.message}`
            : "Status updates are temporarily unavailable. Retrying..."
        );
      }
      return null;
    }
  };

  const schedulePolling = (delay = DEFAULT_POLL_DELAY_MS) => {
    stopPolling();
    pollingRef.current = window.setTimeout(async () => {
      const data = await fetchStatus({ showError: true });
      const currentStatus = data?.status ?? progressStatusRef.current;
      if (["running", "cancelling"].includes(currentStatus)) {
        schedulePolling(getNextPollDelay());
      }
    }, delay);
  };

  useEffect(() => {
    const loadStatus = async () => {
      const data = await fetchStatus();
      if (data && ["running", "cancelling"].includes(data.status)) {
        schedulePolling(DEFAULT_POLL_DELAY_MS);
      }
    };

    const loadLimits = async () => {
      try {
        const data = await requestJson("/api/status");
        if (Number.isInteger(data.max_cluster_count)) {
          setMaxClusterCount(data.max_cluster_count);
        }
      } catch {
        // The backend validates the cluster count, so this is optional.
      }
    };

    void loadStatus();
    void loadLimits();
    return stopPolling;
  }, []);

  useEffect(() => {
    progressStatusRef.current = progress.status;
  }, [progress.status]);

  useEffect(() => {
    const previousStatus = previousProgressStatusRef.current;
    if (
      previousStatus !== progress.status &&
      ["running", "cancelling"].includes(previousStatus) &&
      progress.status === "complete"
    ) {
      setClusterCatalogVersion((currentVersion) => currentVersion + 1);
    }
    previousProgressStatusRef.current = progress.status;
  }, [progress.status]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!["running", "cancelling"].includes(progressStatusRef.current)) {
        return;
      }
      schedulePolling(
        document.visibilityState === "hidden"
          ? HIDDEN_POLL_DELAY_MS
          : DEFAULT_POLL_DELAY_MS
      );
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener(
        "visibilitychange",
        handleVisibilityChange
      );
    };
  }, []);

  const handleIndex = async () => {
    setIndexMessage("");
    const parsedClusterCount = Number.parseInt(clusterCount, 10);
    if (!Number.isInteger(parsedClusterCount) || parsedClusterCount < 1) {
      setIndexMessage("Cluster count must be at least 1.");
      return;
    }
    if (maxClusterCount != null && parsedClusterCount > maxClusterCount) {
      setIndexMessage(`Cluster count must be ${maxClusterCount} or less.`);
      return;
    }

    try {
      const data = await requestJson(
        "/api/index",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            cleanup,
            cluster_count: parsedClusterCount,
          }),
        },
        {
          defaultMessage: "Unable to start indexing.",
          timeoutMessage: "Starting indexing took too long. Try again.",
        }
      );

      pollFailureCountRef.current = 0;
      setProgress(data);
      progressStatusRef.current = data.status;
      syncClusterCount(data.cluster_count);
      stopPolling();
      schedulePolling(DEFAULT_POLL_DELAY_MS);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setIndexMessage("Indexing is already in progress.");
        const data = await fetchStatus({ showError: true });
        if (data && ["running", "cancelling"].includes(data.status)) {
          schedulePolling(DEFAULT_POLL_DELAY_MS);
        }
        return;
      }

      setIndexMessage(error.message);
    }
  };

  const handleCancel = async () => {
    try {
      const data = await requestJson(
        "/api/index/cancel",
        { method: "POST" },
        {
          defaultMessage: "Unable to cancel indexing.",
          timeoutMessage: "Cancel request timed out.",
        }
      );

      progressStatusRef.current = data.status;
      syncClusterCount(data.cluster_count);
      setIndexMessage("");
      setProgress((currentProgress) => ({
        ...currentProgress,
        status: data.status ?? "cancelling",
      }));
      if (["running", "cancelling"].includes(data.status)) {
        schedulePolling(DEFAULT_POLL_DELAY_MS);
      }
    } catch (error) {
      setIndexMessage(error.message);
    }
  };

  const indexing = ["running", "cancelling"].includes(progress.status);
  const hasHeaderStatus = progress.status !== "idle" || Boolean(indexMessage);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-primary">
          <div className="app-brand">
            <h1>FamilyLens</h1>
          </div>

          <nav className="app-nav" aria-label="Primary">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                isActive ? "app-nav-link app-nav-link--active" : "app-nav-link"
              }
            >
              Search
            </NavLink>
            <NavLink
              to="/clusters"
              className={({ isActive }) =>
                isActive ? "app-nav-link app-nav-link--active" : "app-nav-link"
              }
            >
              Clusters
            </NavLink>
          </nav>
        </div>

        <div className="app-header-actions">
          <button
            type="button"
            className="app-index-button"
            onClick={handleIndex}
            disabled={indexing}
          >
            {indexing ? "Indexing..." : "Index Photos"}
          </button>

          <label
            className="app-cluster-count-control"
            htmlFor="cluster-count-input"
          >
            <span>Clusters</span>
            <input
              id="cluster-count-input"
              type="number"
              min="1"
              max={maxClusterCount ?? undefined}
              step="1"
              inputMode="numeric"
              className="app-cluster-count-input"
              value={clusterCount}
              onChange={(e) => setClusterCount(e.target.value)}
              onBlur={() => syncClusterCount(Number.parseInt(clusterCount, 10))}
              disabled={indexing}
            />
          </label>

          <label className="app-cleanup-toggle" title="Remove deleted">
            <input
              type="checkbox"
              checked={cleanup}
              onChange={(e) => setCleanup(e.target.checked)}
              disabled={indexing}
            />
            <span>Remove deleted</span>
          </label>
        </div>

        <div className="app-header-status" aria-live="polite">
          <div
            className={
              hasHeaderStatus
                ? "app-header-status-slot"
                : "app-header-status-slot app-header-status-slot--empty"
            }
          >
            <IndexProgress progress={progress} onCancel={handleCancel} />
            {indexMessage && <div className="app-index-note">{indexMessage}</div>}
          </div>
        </div>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/clusters">
            <Route
              index
              element={<ClustersPage catalogVersion={clusterCatalogVersion} />}
            />
            <Route
              path=":clusterId"
              element={<ClustersPage catalogVersion={clusterCatalogVersion} />}
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
