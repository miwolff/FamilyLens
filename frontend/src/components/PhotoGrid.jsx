import PhotoCard from "./PhotoCard";
import "./PhotoGrid.css";

function PhotoGrid({ results, loading }) {
  if (loading) {
    return <div className="grid-message">Searching...</div>;
  }

  if (results.length === 0) {
    return null;
  }

  return (
    <div className="photo-grid">
      {results.map((result) => (
        <PhotoCard key={result.file_path} result={result} />
      ))}
    </div>
  );
}

export default PhotoGrid;
