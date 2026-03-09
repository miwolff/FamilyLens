import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import PhotoGrid from "../components/PhotoGrid";
import "./ClustersPage.css";

function ClustersPage() {
  const navigate = useNavigate();
  const { clusterId } = useParams();

  const [catalog, setCatalog] = useState({
    status: "loading",
    message: "",
    total_clusters: 0,
    total_photos: 0,
    clusters: [],
  });
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailMessage, setDetailMessage] = useState("");

  useEffect(() => {
    let ignore = false;

    const fetchCatalog = async () => {
      try {
        const res = await fetch("/api/clusters");
        if (!res.ok) {
          throw new Error(`Cluster listing failed: ${res.statusText}`);
        }
        const data = await res.json();
        if (!ignore) {
          setCatalog(data);
          setDetailMessage(data.message || "");
        }
      } catch (err) {
        if (!ignore) {
          setCatalog({
            status: "unavailable",
            message: err.message,
            total_clusters: 0,
            total_photos: 0,
            clusters: [],
          });
          setDetailMessage(err.message);
        }
      }
    };

    fetchCatalog();
    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;

    if (catalog.status !== "ready") {
      setDetail(null);
      return () => {
        ignore = true;
      };
    }

    if (catalog.clusters.length === 0) {
      setDetail(null);
      setDetailMessage("No clusters are available yet.");
      return () => {
        ignore = true;
      };
    }

    if (clusterId == null) {
      navigate(`/clusters/${catalog.clusters[0].cluster_id}`, { replace: true });
      return () => {
        ignore = true;
      };
    }

    const parsedClusterId = Number(clusterId);
    if (!Number.isInteger(parsedClusterId) || parsedClusterId < 0) {
      setDetail(null);
      setDetailMessage("Unknown cluster.");
      return () => {
        ignore = true;
      };
    }

    const fetchDetail = async () => {
      setDetailLoading(true);
      setDetailMessage("");
      try {
        const res = await fetch(`/api/clusters/${parsedClusterId}`);
        if (res.status === 404) {
          throw new Error("Cluster not found.");
        }
        if (res.status === 409) {
          const data = await res.json();
          throw new Error(data.detail || "Clusters are not ready yet.");
        }
        if (!res.ok) {
          throw new Error(`Cluster loading failed: ${res.statusText}`);
        }
        const data = await res.json();
        if (!ignore) {
          setDetail(data);
        }
      } catch (err) {
        if (!ignore) {
          setDetail(null);
          setDetailMessage(err.message);
        }
      } finally {
        if (!ignore) {
          setDetailLoading(false);
        }
      }
    };

    fetchDetail();
    return () => {
      ignore = true;
    };
  }, [catalog, clusterId, navigate]);

  const handleGoToCluster = (nextClusterId) => {
    if (nextClusterId == null) {
      return;
    }
    navigate(`/clusters/${nextClusterId}`);
  };

  const currentClusterNumber = detail ? detail.cluster_id + 1 : null;

  return (
    <div className="clusters-page">
      <div className="clusters-toolbar">
        <button
          type="button"
          className="btn btn-clusters-page"
          onClick={() => navigate("/")}
        >
          Back to Search
        </button>
      </div>

      <section className="clusters-hero">
        <p className="clusters-eyebrow">Largest clusters first</p>
        <h2>Browse visually similar groups of photos</h2>
        <p className="clusters-copy">
          Each cluster groups images that sit close together in embedding space.
          Representative photos appear first, followed by the full gallery for the
          selected cluster.
        </p>
      </section>

      {catalog.status !== "ready" && (
        <div className="message">
          {catalog.message || detailMessage || "Clusters are not ready yet."}
        </div>
      )}

      {catalog.status === "ready" && (
        <>
          <section className="clusters-meta-card">
            <div>
              <p className="clusters-meta-label">Cluster Library</p>
              <p className="clusters-meta-value">
                {catalog.total_clusters} clusters across {catalog.total_photos} photos
              </p>
            </div>
            {detail && (
              <div>
                <p className="clusters-meta-label">Current Cluster</p>
                <p className="clusters-meta-value">
                  {currentClusterNumber} of {detail.total_clusters} · {detail.size} photos
                </p>
              </div>
            )}
          </section>

          <section className="clusters-nav-card">
            <button
              type="button"
              className="btn btn-clusters-page"
              onClick={() => handleGoToCluster(detail?.previous_cluster_id)}
              disabled={!detail || detail.previous_cluster_id == null}
            >
              Previous Cluster
            </button>
            <div className="clusters-nav-copy">
              {detail ? (
                <>
                  <strong>Cluster {currentClusterNumber}</strong>
                  <span>Showing the next closest group in descending size order.</span>
                </>
              ) : (
                <span>{detailLoading ? "Loading cluster…" : detailMessage}</span>
              )}
            </div>
            <button
              type="button"
              className="btn btn-clusters-page"
              onClick={() => handleGoToCluster(detail?.next_cluster_id)}
              disabled={!detail || detail.next_cluster_id == null}
            >
              Next Cluster
            </button>
          </section>

          {detailLoading && <div className="grid-message">Loading cluster…</div>}
          {detailMessage && !detailLoading && <div className="message">{detailMessage}</div>}

          {detail && !detailLoading && (
            <>
              <section className="clusters-section">
                <div className="clusters-section-header">
                  <h3>Representative Photos</h3>
                  <p>
                    The closest photos to this cluster&apos;s center help explain the
                    visual theme.
                  </p>
                </div>
                <PhotoGrid results={detail.representative_photos} loading={false} />
              </section>

              <section className="clusters-section">
                <div className="clusters-section-header">
                  <h3>All Photos In This Cluster</h3>
                  <p>
                    Sorted by closeness to the cluster center, from strongest match
                    to loosest.
                  </p>
                </div>
                <PhotoGrid results={detail.photos} loading={false} />
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}

export default ClustersPage;