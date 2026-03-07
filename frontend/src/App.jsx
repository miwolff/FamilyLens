import { useState, useRef } from "react";
import SearchBar from "./components/SearchBar";
import PhotoGrid from "./components/PhotoGrid";
import IndexProgress from "./components/IndexProgress";
import "./App.css";

function App() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState({ status: "idle" });
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");
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
      if (!res.ok) return;
      const data = await res.json();
      setProgress(data);
      if (["complete", "error", "cancelled"].includes(data.status)) {
        stopPolling();
        if (data.status === "complete" && data.result) {
          setMessage(
            `Indexing complete: ${data.result.indexed} new, ` +
              `${data.result.skipped} skipped, ${data.result.errors} errors. ` +
              `Total: ${data.result.total_in_collection} photos.`
          );
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
        body: JSON.stringify({}),
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
      setProgress((p) => ({ ...p, status: "cancelling" }));
    } catch (_err) {
      // Ignore
    }
  };

  const indexing = ["running", "cancelling"].includes(progress.status);

  return (
    <div className="app">
      <header className="app-header">
        <h1>FamilyLens</h1>
        <p className="subtitle">Search your photos with natural language</p>
      </header>

      <SearchBar
        onSearch={handleSearch}
        onIndex={handleIndex}
        loading={loading}
        indexing={indexing}
      />

      <IndexProgress progress={progress} onCancel={handleCancel} />

      {message && <div className="message">{message}</div>}

      {query && results.length > 0 && (
        <p className="results-count">
          {results.length} results for &ldquo;{query}&rdquo;
        </p>
      )}

      <PhotoGrid results={results} loading={loading} />
    </div>
  );
}

export default App;
