import { useState } from "react";
import PropTypes from "prop-types";
import "./SearchBar.css";

function SearchBar({ onSearch, loading }) {
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
        aria-label="Search the photo library"
        placeholder='Try "birthday party" or "grandma at the lake"'
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
    </form>
  );
}

export default SearchBar;

SearchBar.propTypes = {
  onSearch: PropTypes.func.isRequired,
  loading: PropTypes.bool.isRequired,
};
