import { useState, useMemo } from 'react';
import { SlidersHorizontal, Grid3X3, List, X } from 'lucide-react';
import { AnimatePresence } from 'framer-motion';
import { useItems } from '../hooks/useApi';
import { DealCard } from '../components/DealCard';
import { FilterSidebar } from '../components/FilterSidebar';
import { SortTabs } from '../components/SortTabs';
import { SkeletonGrid } from '../components/SkeletonCard';
import { EmptyDeals } from '../components/EmptyState';
import type { Grade, SortField, ViewMode } from '../types';

export function Deals() {
  // Filter states
  const [grade, setGrade] = useState<Grade>(null);
  const [brand, setBrand] = useState('');
  const [category, setCategory] = useState('');
  const [minPrice, setMinPrice] = useState<number | ''>('');
  const [maxPrice, setMaxPrice] = useState<number | ''>('');
  const [season, setSeason] = useState('');
  const [yearMin, setYearMin] = useState<number | ''>('');
  const [yearMax, setYearMax] = useState<number | ''>('');
  
  // UI states
  const [sort, setSort] = useState<SortField>('profit');
  const [view, setView] = useState<ViewMode>('grid');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  
  // Map sort field to API sort parameter
  const apiSort = useMemo(() => {
    const sortMap: Record<SortField, string> = {
      newest: 'newest',
      profit: 'profit_desc',
      margin: 'margin_desc',
      grade: 'grade_asc',
      velocity: 'sellthrough_desc',
    };
    return sortMap[sort];
  }, [sort]);
  
  // Fetch items with filters
  const { data: items, isLoading } = useItems({
    status: 'active',
    brand: brand || undefined,
    category: category || undefined,
    min_price: minPrice !== '' ? minPrice : undefined,
    max_price: maxPrice !== '' ? maxPrice : undefined,
    season: season || undefined,
    year_min: yearMin !== '' ? yearMin : undefined,
    year_max: yearMax !== '' ? yearMax : undefined,
    sort: apiSort,
    limit: 100,
  });

  // Client-side grade filtering (since API doesn't have grade filter)
  const filteredItems = useMemo(() => {
    if (!items) return [];
    if (!grade) return items;
    return items.filter(item => item.deal_grade === grade);
  }, [items, grade]);

  // Count active filters
  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (grade) count++;
    if (brand) count++;
    if (category) count++;
    if (minPrice !== '' || maxPrice !== '') count++;
    if (season) count++;
    if (yearMin !== '' || yearMax !== '') count++;
    return count;
  }, [grade, brand, category, minPrice, maxPrice, season, yearMin, yearMax]);

  const handleClearFilters = () => {
    setGrade(null);
    setBrand('');
    setCategory('');
    setMinPrice('');
    setMaxPrice('');
    setSeason('');
    setYearMin('');
    setYearMax('');
  };

  // Active filter chips
  const activeFilters = useMemo(() => {
    const filters: { label: string; onRemove: () => void }[] = [];
    
    if (grade) {
      filters.push({
        label: `Grade ${grade}`,
        onRemove: () => setGrade(null),
      });
    }
    if (brand) {
      filters.push({
        label: brand,
        onRemove: () => setBrand(''),
      });
    }
    if (category) {
      filters.push({
        label: category,
        onRemove: () => setCategory(''),
      });
    }
    if (minPrice !== '' || maxPrice !== '') {
      const label = minPrice !== '' && maxPrice !== ''
        ? `$${minPrice} - $${maxPrice}`
        : minPrice !== ''
        ? `$${minPrice}+`
        : `Up to $${maxPrice}`;
      filters.push({
        label,
        onRemove: () => {
          setMinPrice('');
          setMaxPrice('');
        },
      });
    }
    if (season) {
      filters.push({
        label: season,
        onRemove: () => setSeason(''),
      });
    }
    if (yearMin !== '' || yearMax !== '') {
      const label = yearMin !== '' && yearMax !== ''
        ? `${yearMin} - ${yearMax}`
        : yearMin !== ''
        ? `${yearMin}+`
        : `Up to ${yearMax}`;
      filters.push({
        label,
        onRemove: () => {
          setYearMin('');
          setYearMax('');
        },
      });
    }
    
    return filters;
  }, [grade, brand, category, minPrice, maxPrice, season, yearMin, yearMax]);

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile Header */}
      <div className="lg:hidden sticky top-0 z-30 bg-background/95 backdrop-blur border-b border-border px-4 py-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-text-primary">Deals</h1>
          <button
            onClick={() => setSidebarOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-surface rounded-lg text-sm"
          >
            <SlidersHorizontal className="w-4 h-4" />
            Filters
            {activeFiltersCount > 0 && (
              <span className="w-5 h-5 rounded-full bg-accent text-white text-xs flex items-center justify-center">
                {activeFiltersCount}
              </span>
            )}
          </button>
        </div>
      </div>

      <div className="flex">
        {/* Sidebar - Desktop always visible, mobile slide-over */}
        <div className="hidden lg:block">
          <FilterSidebar
            isOpen={true}
            onClose={() => setSidebarOpen(false)}
            grade={grade}
            onGradeChange={setGrade}
            brand={brand}
            onBrandChange={setBrand}
            category={category}
            onCategoryChange={setCategory}
            minPrice={minPrice}
            maxPrice={maxPrice}
            onMinPriceChange={setMinPrice}
            onMaxPriceChange={setMaxPrice}
            season={season}
            onSeasonChange={setSeason}
            yearMin={yearMin}
            yearMax={yearMax}
            onYearMinChange={setYearMin}
            onYearMaxChange={setYearMax}
            activeFiltersCount={activeFiltersCount}
            onClearFilters={handleClearFilters}
          />
        </div>
        
        {/* Mobile Sidebar */}
        <AnimatePresence>
          {sidebarOpen && (
            <FilterSidebar
              isOpen={true}
              onClose={() => setSidebarOpen(false)}
              grade={grade}
              onGradeChange={setGrade}
              brand={brand}
              onBrandChange={setBrand}
              category={category}
              onCategoryChange={setCategory}
              minPrice={minPrice}
              maxPrice={maxPrice}
              onMinPriceChange={setMinPrice}
              onMaxPriceChange={setMaxPrice}
              season={season}
              onSeasonChange={setSeason}
              yearMin={yearMin}
              yearMax={yearMax}
              onYearMinChange={setYearMin}
              onYearMaxChange={setYearMax}
              activeFiltersCount={activeFiltersCount}
              onClearFilters={handleClearFilters}
            />
          )}
        </AnimatePresence>

        {/* Main Content */}
        <main className="flex-1 min-w-0">
          {/* Desktop Header */}
          <div className="hidden lg:block sticky top-0 z-20 bg-background/95 backdrop-blur border-b border-border px-6 py-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold text-text-primary">Deals</h1>
                <p className="text-sm text-text-secondary mt-0.5">
                  {isLoading ? 'Loading...' : `${filteredItems.length} opportunities found`}
                </p>
              </div>

              <div className="flex items-center gap-3">
                {/* Sort */}
                <SortTabs value={sort} onChange={setSort} />

                {/* View Toggle */}
                <div className="flex items-center bg-surface rounded-lg p-1">
                  <button
                    onClick={() => setView('grid')}
                    className={`p-2 rounded-md transition-colors ${
                      view === 'grid' 
                        ? 'bg-surface-hover text-white' 
                        : 'text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    <Grid3X3 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setView('list')}
                    className={`p-2 rounded-md transition-colors ${
                      view === 'list' 
                        ? 'bg-surface-hover text-white' 
                        : 'text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    <List className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* Active Filters Bar */}
            {activeFilters.length > 0 && (
              <div className="flex items-center gap-2 mt-3 flex-wrap">
                <span className="text-xs text-text-secondary">Active:</span>
                {activeFilters.map((filter, index) => (
                  <span
                    key={index}
                    className="inline-flex items-center gap-1 px-2 py-1 bg-accent/10 border border-accent/20 rounded-full text-xs text-accent"
                  >
                    {filter.label}
                    <button 
                      onClick={filter.onRemove}
                      className="hover:text-white transition-colors"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
                <button
                  onClick={handleClearFilters}
                  className="text-xs text-text-secondary hover:text-text-primary transition-colors ml-1"
                >
                  Clear all
                </button>
              </div>
            )}
          </div>

          {/* Mobile Sort Bar */}
          <div className="lg:hidden px-4 py-3 border-b border-border">
            <SortTabs value={sort} onChange={setSort} />
          </div>

          {/* Results */}
          <div className="p-4 lg:p-6">
            {isLoading ? (
              <SkeletonGrid count={8} view={view} />
            ) : filteredItems.length === 0 ? (
              <EmptyDeals onClearFilters={handleClearFilters} />
            ) : (
              <div className={`grid gap-4 ${
                view === 'grid'
                  ? 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4'
                  : 'grid-cols-1 max-w-4xl'
              }`}>
                {filteredItems.map((item) => (
                  <DealCard key={item.id} item={item} view={view} />
                ))}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
