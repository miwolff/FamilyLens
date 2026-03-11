import { useState } from "react";
import PropTypes from "prop-types";
import "./SearchBar.css";

function SearchBar({
  onSearch,
  onIndex,
  loading,
  indexing,
  cleanup,
  onCleanupChange,
}) {
  const [input, setInput] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch(input);
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <div className="search-bar-primary">
        <label className="search-field">
          <span className="search-field-label">Search the photo library</span>
          <input
            type="text"
            className="search-input"
            placeholder='Try "birthday party", "beach sunset", or "grandma at the lake"'
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
        </label>

        <div className="search-actions">
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
        </div>
      </div>

      <div className="search-bar-utility">
        <label className="cleanup-label">
          <input
            type="checkbox"
            checked={cleanup}
            onChange={(e) => onCleanupChange(e.target.checked)}
            disabled={indexing}
          />
          <span>Remove deleted files from index</span>
        </label>
        <span className="search-bar-note">
          Use this after moving or deleting photos on disk.
        </span>
      </div>
    </form>
  );
}

export default SearchBar;

SearchBar.propTypes = {
  onSearch: PropTypes.func.isRequired,
  onIndex: PropTypes.func.isRequired,
  loading: PropTypes.bool.isRequired,
  indexing: PropTypes.bool.isRequired,
  cleanup: PropTypes.bool.isRequired,
  onCleanupChange: PropTypes.func.isRequired,
};
