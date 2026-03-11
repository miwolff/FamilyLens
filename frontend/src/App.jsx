import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import ClustersPage from "./pages/ClustersPage";
import IndexProgress from "./components/IndexProgress";
import SearchPage from "./pages/SearchPage";
import "./App.css";

const DEFAULT_CLUSTER_COUNT = 24;

function App() {
  const [progress, setProgress] = useState({ status: "idle", stage: "idle" });
  const [cleanup, setCleanup] = useState(false);
  const [clusterCount, setClusterCount] = useState(String(DEFAULT_CLUSTER_COUNT));
  const [indexMessage, setIndexMessage] = useState("");
  const [clusterCatalogVersion, setClusterCatalogVersion] = useState(0);
  const pollingRef = useRef(null);
  const previousProgressStatusRef = useRef("idle");

  const syncClusterCount = (nextClusterCount) => {
    if (Number.isInteger(nextClusterCount) && nextClusterCount > 0) {
      setClusterCount(String(nextClusterCount));
    }
  };

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/index/status");
      if (!res.ok) {
        return null;
      }

      const data = await res.json();
      setProgress(data);
      syncClusterCount(data.cluster_count);
      if (data.status !== "idle") {
        setIndexMessage("");
      }
      if (["complete", "error", "cancelled"].includes(data.status)) {
        stopPolling();
      }
      return data;
    } catch (_err) {
      return null;
    }
  };

  useEffect(() => {
    const loadStatus = async () => {
      const data = await fetchStatus();
      if (
        data &&
        ["running", "cancelling"].includes(data.status) &&
        !pollingRef.current
      ) {
        pollingRef.current = setInterval(fetchStatus, 1000);
      }
    };

    void loadStatus();
    return stopPolling;
  }, []);

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

  const handleIndex = async () => {
    setIndexMessage("");
    const parsedClusterCount = Number.parseInt(clusterCount, 10);
    if (!Number.isInteger(parsedClusterCount) || parsedClusterCount < 1) {
      setIndexMessage("Cluster count must be at least 1.");
      return;
    }

    try {
      const res = await fetch("/api/index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cleanup,
          cluster_count: parsedClusterCount,
        }),
      });
      if (res.status === 409) {
        setIndexMessage("Indexing is already in progress.");
        const data = await fetchStatus();
        if (
          data &&
          ["running", "cancelling"].includes(data.status) &&
          !pollingRef.current
        ) {
          pollingRef.current = setInterval(fetchStatus, 1000);
        }
        return;
      }
      if (!res.ok) {
        throw new Error(`Indexing failed: ${res.statusText}`);
      }

      const data = await res.json();
      setProgress(data);
      syncClusterCount(data.cluster_count);
      stopPolling();
      pollingRef.current = setInterval(fetchStatus, 1000);
    } catch (err) {
      setIndexMessage(`Error: ${err.message}`);
    }
  };

  const handleCancel = async () => {
    try {
      await fetch("/api/index/cancel", { method: "POST" });
      setProgress((currentProgress) => ({
        ...currentProgress,
        status: "cancelling",
      }));
    } catch (_err) {
      // Ignore transient cancel errors.
    }
  };

  const indexing = ["running", "cancelling"].includes(progress.status);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-brand">
          <h1>FamilyLens</h1>
        </div>

        <div className="app-top-controls">
          <label className="app-cluster-count-control" htmlFor="cluster-count-input">
            <span>Clusters</span>
            <input
              id="cluster-count-input"
              type="number"
              min="1"
              step="1"
              inputMode="numeric"
              className="app-cluster-count-input"
              value={clusterCount}
              onChange={(e) => setClusterCount(e.target.value)}
              onBlur={() => syncClusterCount(Number.parseInt(clusterCount, 10))}
              disabled={indexing}
            />
          </label>

          <label className="app-cleanup-toggle" title="Remove deleted files from index">
            <input
              type="checkbox"
              checked={cleanup}
              onChange={(e) => setCleanup(e.target.checked)}
              disabled={indexing}
            />
            <span>Remove deleted files</span>
          </label>

          <button
            type="button"
            className="app-index-button"
            onClick={handleIndex}
            disabled={indexing}
          >
            {indexing ? "Indexing..." : "Index Photos"}
          </button>

          <IndexProgress progress={progress} onCancel={handleCancel} />
          {indexMessage && <div className="app-index-note">{indexMessage}</div>}
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
