import { getCategoryDescription } from "../content/catalogMetadata";

type OverviewPageProps = {
  healthStatus: string;
  categories: string[];
  isLoading: boolean;
  onOpenCategory: (category: string) => void;
};

export default function OverviewPage({
  healthStatus,
  categories,
  isLoading,
  onOpenCategory,
}: OverviewPageProps) {
  return (
    <div className="page-grid">
      <div className="panel hero-panel">
        <p className="eyebrow">Experimental Catalog</p>
        <h1>Overview</h1>
        <p className="muted">
          Lightweight browser for the experimental catalog exposed by the HTTP API.
        </p>
        <div className="health-row">
          <span className="health-label">API health</span>
          <span className={`health-badge health-${healthStatus}`}>{healthStatus}</span>
        </div>
      </div>

      <div className="panel">
        <h2>Categories</h2>
        {isLoading ? (
          <p className="loading-text">Loading catalog overview...</p>
        ) : (
          <div className="overview-cards">
            {categories.map((category) => (
              <button key={category} className="overview-card" onClick={() => onOpenCategory(category)} type="button">
                <strong className="primary-label">{getCategoryDescription(category).title}</strong>
                <span className="overview-card-id">{category}</span>
                <span>{getCategoryDescription(category).whatIsIt}</span>
                <span className="muted">{getCategoryDescription(category).whatIsItFor}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
