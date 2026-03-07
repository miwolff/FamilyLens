import { useState } from "react";
import SearchBar from "./components/SearchBar";
import PhotoGrid from "./components/PhotoGrid";
import "./App.css";

function App() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");

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
    setIndexing(true);
    setMessage("Indexing photos... this may take a while.");
    try {
      const res = await fetch("/api/index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error(`Indexing failed: ${res.statusText}`);
      const data = await res.json();
      setMessage(
        `Indexing complete: ${data.indexed} new, ${data.skipped} skipped, ` +
          `${data.errors} errors. Total: ${data.total_in_collection} photos.`
      );
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setIndexing(false);
    }
  };

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
