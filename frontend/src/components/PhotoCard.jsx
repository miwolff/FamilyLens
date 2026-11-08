import PropTypes from "prop-types";
import "./PhotoCard.css";

function PhotoCard({ result }) {
  const scorePercent = (result.score * 100).toFixed(1);
  const imageUrl =
    "/api/photos/" +
    result.file_path.split("/").map(encodeURIComponent).join("/");
  const imageAlt = result.filename
    ? `Photo result ${result.filename}`
    : "Photo result";

  return (
    <div className="photo-card" title={result.file_path}>
      <div className="photo-wrapper">
        <img
          src={imageUrl}
          alt={imageAlt}
          className="photo-img"
          loading="lazy"
        />
        <span className="score-badge" aria-label={`${scorePercent}% match`}>
          {scorePercent}%
        </span>
      </div>
    </div>
  );
}

export default PhotoCard;

PhotoCard.propTypes = {
  result: PropTypes.shape({
    file_path: PropTypes.string.isRequired,
    filename: PropTypes.string.isRequired,
    score: PropTypes.number.isRequired,
  }).isRequired,
};
