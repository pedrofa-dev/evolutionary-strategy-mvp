import type { CatalogItem } from "../types/catalog";

type CatalogItemCardProps = {
  item: CatalogItem;
  onOpen: (item: CatalogItem) => void;
};

export default function CatalogItemCard({ item, onOpen }: CatalogItemCardProps) {
  return (
    <button className="item-card" onClick={() => onOpen(item)} type="button">
      <div className="item-card-header">
        <strong>{item.id}</strong>
        <span className={`origin-tag origin-${item.origin}`}>{item.origin}</span>
      </div>
      <div className="item-card-meta">{item.category}</div>
      <div className="item-card-description">
        {item.description ?? "No description available."}
      </div>
    </button>
  );
}
