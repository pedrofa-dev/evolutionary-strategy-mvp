import CatalogItemDetail from "../components/CatalogItemDetail";
import type { CatalogItem } from "../types/catalog";

type DetailPageProps = {
  item: CatalogItem | null;
  onBackToCategory: (category: string) => void;
};

export default function DetailPage({ item, onBackToCategory }: DetailPageProps) {
  return (
    <div className="page-grid">
      <div className="panel">
        <h2>Navigation</h2>
        {item ? (
          <button
            className="link-button"
            onClick={() => onBackToCategory(item.category)}
            type="button"
          >
            Back to {item.category}
          </button>
        ) : (
          <p className="muted">No item selected.</p>
        )}
      </div>
      <CatalogItemDetail item={item} />
    </div>
  );
}
