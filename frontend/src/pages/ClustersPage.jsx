import { useEffect, useState } from "react";
import PropTypes from "prop-types";
import { useNavigate, useParams } from "react-router-dom";

import PhotoGrid from "../components/PhotoGrid";
import { requestJson } from "../lib/api";
import "./ClustersPage.css";

function ClustersPage({ catalogVersion }) {
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
        const data = await requestJson("/api/clusters", {}, {
          defaultMessage: "Unable to load clusters.",
          timeoutMessage: "Loading clusters took too long.",
        });
        if (!ignore) {
          setCatalog(data);
          setDetailMessage(data.message || "");
        }
      } catch (error) {
        if (!ignore) {
          setCatalog({
            status: "unavailable",
            message: error.message,
            total_clusters: 0,
            total_photos: 0,
            clusters: [],
          });
          setDetailMessage(error.message);
        }
      }
    };

    fetchCatalog();
    return () => {
      ignore = true;
    };
  }, [catalogVersion]);

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

    if (parsedClusterId >= catalog.total_clusters) {
      navigate(`/clusters/${catalog.clusters[0].cluster_id}`, { replace: true });
      return () => {
        ignore = true;
      };
    }

    const fetchDetail = async () => {
      setDetailLoading(true);
      setDetailMessage("");
      try {
        const data = await requestJson(`/api/clusters/${parsedClusterId}`, {}, {
          defaultMessage: "Unable to load the selected cluster.",
          timeoutMessage: "Loading the selected cluster took too long.",
        });
        if (!ignore) {
          setDetail(data);
        }
      } catch (error) {
        if (!ignore) {
          setDetail(null);
          setDetailMessage(error.message);
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

  const selectedClusterId = detail?.cluster_id ?? "";

  return (
    <div className="clusters-page">
      {catalog.status !== "ready" && (
        <div className="message">
          {catalog.message || detailMessage || "Clusters are not ready yet."}
        </div>
      )}

      {catalog.status === "ready" && (
        <>
          <section className="clusters-toolbar">
            <button
              type="button"
              className="btn btn-clusters-page"
              onClick={() => handleGoToCluster(detail?.previous_cluster_id)}
              disabled={!detail || detail.previous_cluster_id == null}
            >
              Previous Cluster
            </button>

            <label className="clusters-picker" htmlFor="cluster-picker">
              <span className="clusters-picker-label">
                {catalog.total_clusters} clusters · {catalog.total_photos} photos
              </span>
              <select
                id="cluster-picker"
                className="clusters-picker-select"
                value={selectedClusterId}
                onChange={(e) => handleGoToCluster(Number(e.target.value))}
                disabled={detailLoading || catalog.clusters.length === 0}
              >
                {catalog.clusters.map((cluster) => (
                  <option key={cluster.cluster_id} value={cluster.cluster_id}>
                    {`Cluster ${cluster.cluster_id + 1} · ${cluster.size} photos`}
                  </option>
                ))}
              </select>
            </label>

            {!detail && detailMessage && !detailLoading && (
              <div className="clusters-stat clusters-stat--status">
                <span className="clusters-stat-label">Status</span>
                <strong>{detailMessage}</strong>
              </div>
            )}

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
            <PhotoGrid
              results={detail.photos}
              loading={false}
              label={`Photos in cluster ${detail.cluster_id + 1}`}
            />
          )}
        </>
      )}
    </div>
  );
}

export default ClustersPage;

ClustersPage.propTypes = {
  catalogVersion: PropTypes.number.isRequired,
};