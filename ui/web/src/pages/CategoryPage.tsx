import CategoryList from "../components/CategoryList";
import CatalogItemCard from "../components/CatalogItemCard";
import { getCategoryDescription } from "../content/catalogMetadata";
import type { CatalogItem } from "../types/catalog";

type CategoryPageProps = {
  categories: string[];
  selectedCategory: string;
  items: CatalogItem[];
  isLoading: boolean;
  onSelectCategory: (category: string) => void;
  onOpenItem: (item: CatalogItem) => void;
};

export default function CategoryPage({
  categories,
  selectedCategory,
  items,
  isLoading,
  onSelectCategory,
  onOpenItem,
}: CategoryPageProps) {
  const description = getCategoryDescription(selectedCategory);

  return (
    <div className="page-grid category-layout">
      <CategoryList
        categories={categories}
        selectedCategory={selectedCategory}
        onSelectCategory={onSelectCategory}
      />

      <div className="panel">
        <h2>{description.title}</h2>
        <p className="category-id">{selectedCategory}</p>
        <div className="category-explainer">
          <p>
            <strong>What is it?</strong> {description.whatIsIt}
          </p>
          <p>
            <strong>What is it for?</strong> {description.whatIsItFor}
          </p>
        </div>
        {isLoading ? (
          <p className="loading-text">Loading category items...</p>
        ) : items.length === 0 ? (
          <p className="muted">This category is empty.</p>
        ) : (
          <div className="item-list">
            {items.map((item) => (
              <CatalogItemCard key={item.id} item={item} onOpen={onOpenItem} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
