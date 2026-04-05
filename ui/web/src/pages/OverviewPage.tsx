type OverviewPageProps = {
  healthStatus: string;
  categories: string[];
  onOpenCategory: (category: string) => void;
};

export default function OverviewPage({
  healthStatus,
  categories,
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
        <div className="overview-cards">
          {categories.map((category) => (
            <button
              key={category}
              className="overview-card"
              onClick={() => onOpenCategory(category)}
              type="button"
            >
              <strong>{category}</strong>
              <span>Open category</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
