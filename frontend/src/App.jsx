import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import ClustersPage from "./pages/ClustersPage";
import IndexProgress from "./components/IndexProgress";
import SearchPage from "./pages/SearchPage";
import "./App.css";

function App() {
  const [progress, setProgress] = useState({ status: "idle", stage: "idle" });
  const [cleanup, setCleanup] = useState(false);
  const [indexMessage, setIndexMessage] = useState("");
  const pollingRef = useRef(null);

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

  const handleIndex = async () => {
    setIndexMessage("");
    try {
      const res = await fetch("/api/index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cleanup }),
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
            <Route index element={<ClustersPage />} />
            <Route path=":clusterId" element={<ClustersPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
