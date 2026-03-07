import "./PhotoCard.css";

function PhotoCard({ result }) {
  const scorePercent = (result.score * 100).toFixed(1);
  const imageUrl = `/api/photos/${encodeURIComponent(result.file_path)}`;

  return (
    <div className="photo-card">
      <div className="photo-wrapper">
        <img
          src={imageUrl}
          alt={result.filename}
          className="photo-img"
          loading="lazy"
        />
        <span className="score-badge">{scorePercent}%</span>
      </div>
      <div className="photo-info">
        <span className="photo-filename" title={result.file_path}>
          {result.filename}
        </span>
      </div>
    </div>
  );
}

export default PhotoCard;
