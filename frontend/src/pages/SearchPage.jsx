import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import IndexProgress from "../components/IndexProgress";
import PhotoGrid from "../components/PhotoGrid";
import SearchBar from "../components/SearchBar";

function SearchPage() {
  const navigate = useNavigate();
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState({ status: "idle", stage: "idle" });
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");
  const [cleanup, setCleanup] = useState(false);
  const pollingRef = useRef(null);

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  useEffect(() => stopPolling, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/index/status");
      if (!res.ok) return;
      const data = await res.json();
      setProgress(data);
      if (["complete", "error", "cancelled"].includes(data.status)) {
        stopPolling();
        if (data.status === "complete" && data.result) {
          const baseMessage =
            `Indexing complete: ${data.result.indexed} new, ` +
            `${data.result.skipped} skipped, ${data.result.errors} errors. ` +
            `Total: ${data.result.total_in_collection} photos.`;
          if (data.cluster_error) {
            setMessage(`${baseMessage} Clusters unavailable: ${data.cluster_error}`);
          } else {
            setMessage(
              `${baseMessage} Built ${data.result.total_clusters} clusters.`
            );
          }
        } else if (data.status === "cancelled") {
          setMessage("Indexing cancelled.");
        } else if (data.status === "error") {
          setMessage("Indexing failed. Check server logs.");
        }
      }
    } catch (_err) {
      // Ignore transient polling errors
    }
  };

  const handleSearch = async (searchQuery) => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setMessage("");
    setQuery(searchQuery);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery, limit: 40 }),
      });
      if (!res.ok) throw new Error(`Search failed: ${res.statusText}`);
      const data = await res.json();
      setResults(data.results);
      if (data.results.length === 0) {
        setMessage("No matching photos found. Try a different query.");
      }
    } catch (err) {
      setMessage(`Error: ${err.message}`);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleIndex = async () => {
    setMessage("");
    try {
      const res = await fetch("/api/index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cleanup }),
      });
      if (res.status === 409) {
        setMessage("Indexing is already in progress.");
        return;
      }
      if (!res.ok) throw new Error(`Indexing failed: ${res.statusText}`);
      const data = await res.json();
      setProgress(data);
      stopPolling();
      pollingRef.current = setInterval(fetchStatus, 1000);
    } catch (err) {
      setMessage(`Error: ${err.message}`);
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
      // Ignore
    }
  };

  const indexing = ["running", "cancelling"].includes(progress.status);

  return (
    <>
      <SearchBar
        onSearch={handleSearch}
        onIndex={handleIndex}
        onBrowseClusters={() => navigate("/clusters")}
        loading={loading}
        indexing={indexing}
        cleanup={cleanup}
        onCleanupChange={setCleanup}
      />

      <IndexProgress progress={progress} onCancel={handleCancel} />

      {message && <div className="message">{message}</div>}

      {query && results.length > 0 && (
        <p className="results-count">
          {results.length} results for &ldquo;{query}&rdquo;
        </p>
      )}

      <PhotoGrid results={results} loading={loading} />
    </>
  );
}

export default SearchPage;