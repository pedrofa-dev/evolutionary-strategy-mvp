import CategoryList from "../components/CategoryList";
import CatalogItemCard from "../components/CatalogItemCard";
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
  return (
    <div className="page-grid category-layout">
      <CategoryList
        categories={categories}
        selectedCategory={selectedCategory}
        onSelectCategory={onSelectCategory}
      />

      <div className="panel">
        <h2>{selectedCategory}</h2>
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
