import PropTypes from "prop-types";
import PhotoCard from "./PhotoCard";
import "./PhotoGrid.css";

function PhotoGrid({ results, loading, label = "Photo results" }) {
  if (loading) {
    return (
      <div className="grid-message" role="status" aria-live="polite">
        Searching...
      </div>
    );
  }

  if (results.length === 0) {
    return null;
  }

  return (
    <div className="photo-grid" role="region" aria-live="polite" aria-label={label}>
      {results.map((result) => (
        <PhotoCard key={result.file_path} result={result} />
      ))}
    </div>
  );
}

export default PhotoGrid;

PhotoGrid.propTypes = {
  results: PropTypes.arrayOf(
    PropTypes.shape({
      file_path: PropTypes.string.isRequired,
      filename: PropTypes.string.isRequired,
      score: PropTypes.number.isRequired,
    })
  ).isRequired,
  loading: PropTypes.bool.isRequired,
  label: PropTypes.string,
};
