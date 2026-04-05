import { getCategoryDescription } from "../content/catalogMetadata";

type CategoryListProps = {
  categories: string[];
  selectedCategory: string | null;
  onSelectCategory: (category: string) => void;
};

export default function CategoryList({
  categories,
  selectedCategory,
  onSelectCategory,
}: CategoryListProps) {
  return (
    <div className="panel">
      <h2>Categories</h2>
      {categories.length === 0 ? (
        <p className="muted">No catalog categories available.</p>
      ) : (
        <ul className="category-list">
          {categories.map((category) => (
            <li key={category}>
              <button
                className={category === selectedCategory ? "category-button active" : "category-button"}
                onClick={() => onSelectCategory(category)}
                type="button"
              >
                <span className="category-button-label">
                  {getCategoryDescription(category).title}
                </span>
                <span className="category-button-id">{category}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
