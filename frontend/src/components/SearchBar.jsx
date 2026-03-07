import { useState } from "react";
import "./SearchBar.css";

function SearchBar({ onSearch, onIndex, loading, indexing }) {
  const [input, setInput] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch(input);
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        className="search-input"
        placeholder='Search photos... (e.g. "birthday party", "beach sunset")'
        value={input}
        onChange={(e) => setInput(e.target.value)}
        disabled={loading}
      />
      <button
        type="submit"
        className="btn btn-search"
        disabled={loading || !input.trim()}
      >
        {loading ? "Searching..." : "Search"}
      </button>
      <button
        type="button"
        className="btn btn-index"
        onClick={onIndex}
        disabled={indexing}
      >
        {indexing ? "Indexing..." : "Index Photos"}
      </button>
    </form>
  );
}

export default SearchBar;
