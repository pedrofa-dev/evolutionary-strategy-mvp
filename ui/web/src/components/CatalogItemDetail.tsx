import type { CatalogItem } from "../types/catalog";
import {
  describeOrigin,
  getCategoryDescription,
  getDisplayLabel,
} from "../content/catalogMetadata";

type CatalogItemDetailProps = {
  item: CatalogItem | null;
  notFoundMessage?: string | null;
};

export default function CatalogItemDetail({
  item,
  notFoundMessage = null,
}: CatalogItemDetailProps) {
  if (!item) {
    return (
      <div className="panel detail-panel">
        <h2>Detail</h2>
        <p className="muted">
          {notFoundMessage ?? "Select an item to inspect its metadata."}
        </p>
      </div>
    );
  }

  const itemLabel = getDisplayLabel(item.id, item.payload);
  const categoryLabel = getCategoryDescription(item.category).title;

  return (
    <div className="panel detail-panel">
      <h2>{itemLabel}</h2>
      <p className="detail-id">{item.id}</p>
      <dl className="detail-grid">
        <dt>Category</dt>
        <dd>{categoryLabel}</dd>
        <dt>Origin</dt>
        <dd>{describeOrigin(item.origin)}</dd>
        <dt>Description</dt>
        <dd>
          {item.description ?? "No description available. This may be a raw or experimental entry."}
        </dd>
      </dl>
      {!item.description ? <div className="soft-warning">This entry does not include a human description yet.</div> : null}
      <div className="explanation-panel">
        <h3>What is this?</h3>
        <p>
          This entry is part of the experimental catalog and represents a named
          module, asset, or runtime-provided definition.
        </p>
        <h3>Why does it exist?</h3>
        <p>
          It helps make the system inspectable so experiments can be understood,
          compared, and eventually composed through a UI.
        </p>
      </div>
      <div className="technical-meta">
        <span className="technical-meta-label">Technical metadata</span>
        <code>{item.file_path ?? "No file path"}</code>
      </div>
      <h3>Payload</h3>
      <pre className="json-block">{JSON.stringify(item.payload, null, 2)}</pre>
    </div>
  );
}
