import type { CatalogItem } from "../types/catalog";

type CatalogItemDetailProps = {
  item: CatalogItem | null;
};

export default function CatalogItemDetail({ item }: CatalogItemDetailProps) {
  if (!item) {
    return (
      <div className="panel detail-panel">
        <h2>Detail</h2>
        <p className="muted">Select an item to inspect its metadata.</p>
      </div>
    );
  }

  return (
    <div className="panel detail-panel">
      <h2>Detail</h2>
      <dl className="detail-grid">
        <dt>ID</dt>
        <dd>{item.id}</dd>
        <dt>Category</dt>
        <dd>{item.category}</dd>
        <dt>Origin</dt>
        <dd>{item.origin}</dd>
        <dt>Description</dt>
        <dd>{item.description ?? "No description"}</dd>
        <dt>File Path</dt>
        <dd>{item.file_path ?? "No file path"}</dd>
      </dl>
      <h3>Payload</h3>
      <pre className="json-block">{JSON.stringify(item.payload, null, 2)}</pre>
    </div>
  );
}
