import { useState } from "react";
import PhotoGrid from "../components/PhotoGrid";
import SearchBar from "../components/SearchBar";
import { requestJson } from "../lib/api";
import "./SearchPage.css";

function SearchPage() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");

  const handleSearch = async (searchQuery) => {
    const normalizedQuery = searchQuery.trim();
    if (!normalizedQuery) return;

    setLoading(true);
    setMessage("");
    setQuery(normalizedQuery);
    try {
      const data = await requestJson(
        "/api/search",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: normalizedQuery, limit: 40 }),
        },
        {
          defaultMessage: "Unable to run the search.",
          timeoutMessage: "Search took too long. Try a more specific query.",
        }
      );

      setResults(data.results);
      if (data.results.length === 0) {
        setMessage("No matching photos found. Try a different query.");
      }
    } catch (error) {
      setMessage(error.message);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="search-page">
      <SearchBar onSearch={handleSearch} loading={loading} />

      <div className="search-page-summary" aria-live="polite">
        {query && results.length > 0 && (
          <p className="results-count">
            {results.length} results for &ldquo;{query}&rdquo;
          </p>
        )}
        {message && <div className="message">{message}</div>}
      </div>

      <PhotoGrid results={results} loading={loading} label="Search results" />
    </div>
  );
}

export default SearchPage;