import CatalogItemDetail from "../components/CatalogItemDetail";
import { formatHumanLabel } from "../content/catalogMetadata";
import type { CatalogItem } from "../types/catalog";

type DetailPageProps = {
  item: CatalogItem | null;
  category: string;
  isLoading: boolean;
  missingItemId?: string | null;
  onBackToCategory: (category: string) => void;
  onBackToOverview: () => void;
};

export default function DetailPage({
  item,
  category,
  isLoading,
  missingItemId = null,
  onBackToCategory,
  onBackToOverview,
}: DetailPageProps) {
  const notFoundMessage = missingItemId
    ? `Item '${missingItemId}' was not found in this category.`
    : null;

  return (
    <div className="page-grid">
      <div className="panel">
        <h2>Navigation</h2>
        {item || missingItemId ? (
          <div className="nav-actions">
            <button
              className="link-button"
              onClick={() => onBackToCategory(category)}
              type="button"
            >
              Back to {formatHumanLabel(category)}
            </button>
            <button className="link-button secondary" onClick={onBackToOverview} type="button">
              Back to overview
            </button>
          </div>
        ) : (
          <p className="muted">No item selected.</p>
        )}
      </div>
      {isLoading ? (
        <div className="panel detail-panel">
          <h2>Detail</h2>
          <p className="loading-text">Loading item detail...</p>
        </div>
      ) : (
        <CatalogItemDetail item={item} notFoundMessage={notFoundMessage} />
      )}
    </div>
  );
}
