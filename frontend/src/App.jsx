import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import ClustersPage from "./pages/ClustersPage";
import SearchPage from "./pages/SearchPage";
import "./App.css";

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>FamilyLens</h1>
          <p className="subtitle">
            Search your photos with natural language and browse visual clusters
          </p>
        </div>
        <nav className="app-nav" aria-label="Primary">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              isActive ? "app-nav-link app-nav-link--active" : "app-nav-link"
            }
          >
            Search
          </NavLink>
          <NavLink
            to="/clusters"
            className={({ isActive }) =>
              isActive ? "app-nav-link app-nav-link--active" : "app-nav-link"
            }
          >
            Clusters
          </NavLink>
        </nav>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/clusters">
            <Route index element={<ClustersPage />} />
            <Route path=":clusterId" element={<ClustersPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
