import { useState } from "react";
import PhotoGrid from "../components/PhotoGrid";
import SearchBar from "../components/SearchBar";
import "./SearchPage.css";

function SearchPage() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
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

  return (
    <div className="search-page">
      <SearchBar onSearch={handleSearch} loading={loading} />

      <div className="search-page-summary">
        {query && results.length > 0 && (
          <p className="results-count">
            {results.length} results for &ldquo;{query}&rdquo;
          </p>
        )}
        {message && <div className="message">{message}</div>}
      </div>

      <PhotoGrid results={results} loading={loading} />
    </div>
  );
}

export default SearchPage;