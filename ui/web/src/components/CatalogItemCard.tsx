import type { CatalogItem } from "../types/catalog";
import {
  describeOrigin,
  getDisplayLabel,
  getCategoryDescription,
} from "../content/catalogMetadata";

type CatalogItemCardProps = {
  item: CatalogItem;
  onOpen: (item: CatalogItem) => void;
};

export default function CatalogItemCard({ item, onOpen }: CatalogItemCardProps) {
  const hasDescription = Boolean(item.description);
  const itemLabel = getDisplayLabel(item.id, item.payload);
  const categoryLabel = getCategoryDescription(item.category).title;

  return (
    <button className="item-card" onClick={() => onOpen(item)} type="button">
      <div className="item-card-header">
        <div>
          <strong className="primary-label">{itemLabel}</strong>
          <div className="item-card-id">{item.id}</div>
        </div>
        <span className={`origin-tag origin-${item.origin}`}>{describeOrigin(item.origin)}</span>
      </div>
      <div className="item-card-meta">{categoryLabel}</div>
      <div className="item-card-description">
        {item.description ?? "No description available. This may be a raw or experimental entry."}
      </div>
      {!hasDescription ? <div className="soft-warning">Description missing</div> : null}
    </button>
  );
}
