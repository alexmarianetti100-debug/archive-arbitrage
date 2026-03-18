import { useState, useMemo, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { SlidersHorizontal, Grid3X3, List, X, ChevronDown, Clock } from 'lucide-react';
import { AnimatePresence } from 'framer-motion';
import { useItems, useScrapeHistory } from '../hooks/useApi';
import { DealCard } from '../components/DealCard';
import { FilterSidebar } from '../components/FilterSidebar';
import { SortTabs } from '../components/SortTabs';
import { SkeletonGrid } from '../components/SkeletonCard';
import { EmptyDeals } from '../components/EmptyState';
import { ItemDetailPanel } from '../components/ItemDetailPanel';
import type { Item, Grade, SortField, ViewMode } from '../types';

function useFilterParam(searchParams: URLSearchParams, key: string, fallback: string = ''): string {
  return searchParams.get(key) || fallback;
}

function useNumericParam(searchParams: URLSearchParams, key: string): number | '' {
  const val = searchParams.get(key);
  if (val === null || val === '') return '';
  const n = Number(val);
  return isNaN(n) ? '' : n;
}

export function Deals() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Read initial state from URL params
  const grade = (useFilterParam(searchParams, 'grade') || null) as Grade;
  const brand = useFilterParam(searchParams, 'brand');
  const category = useFilterParam(searchParams, 'category');
  const minPrice = useNumericParam(searchParams, 'min_price');
  const maxPrice = useNumericParam(searchParams, 'max_price');
  const season = useFilterParam(searchParams, 'season');
  const yearMin = useNumericParam(searchParams, 'year_min');
  const yearMax = useNumericParam(searchParams, 'year_max');
  const sort = (useFilterParam(searchParams, 'sort', 'newest') as SortField);
  const needsReview = searchParams.get('needs_review') === '1';

  // UI-only state (not persisted to URL)
  const [view, setView] = useState<ViewMode>('grid');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const PAGE_SIZE = 48;
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);

  const { data: historyData } = useScrapeHistory();

  // Helper to update a single URL param without clobbering others
  const setParam = useCallback((key: string, value: string | number | null) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (value === null || value === '' || value === undefined) {
        next.delete(key);
      } else {
        next.set(key, String(value));
      }
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  // Filter setters that write to URL
  const setGrade = useCallback((v: Grade) => setParam('grade', v), [setParam]);
  const setBrand = useCallback((v: string) => setParam('brand', v), [setParam]);
  const setCategory = useCallback((v: string) => setParam('category', v), [setParam]);
  const setMinPrice = useCallback((v: number | '') => setParam('min_price', v === '' ? null : v), [setParam]);
  const setMaxPrice = useCallback((v: number | '') => setParam('max_price', v === '' ? null : v), [setParam]);
  const setSeason = useCallback((v: string) => setParam('season', v), [setParam]);
  const setYearMin = useCallback((v: number | '') => setParam('year_min', v === '' ? null : v), [setParam]);
  const setYearMax = useCallback((v: number | '') => setParam('year_max', v === '' ? null : v), [setParam]);
  const setSort = useCallback((v: SortField) => setParam('sort', v === 'newest' ? null : v), [setParam]);

  const handleLoadMore = useCallback(() => {
    setVisibleCount((prev) => prev + PAGE_SIZE);
  }, []);

  // Reset visible count when filters change
  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [grade, brand, category, minPrice, maxPrice, season, yearMin, yearMax, sort, needsReview]);

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

  const { data: items, isLoading } = useItems({
    brand: brand || undefined,
    category: category || undefined,
    min_price: minPrice !== '' ? minPrice : undefined,
    max_price: maxPrice !== '' ? maxPrice : undefined,
    season: season || undefined,
    year_min: yearMin !== '' ? yearMin : undefined,
    year_max: yearMax !== '' ? yearMax : undefined,
    needs_review: needsReview || undefined,
    sort: apiSort,
    page_size: 500,
  });

  const filteredItems = useMemo(() => {
    if (!items) return [];
    if (!grade) return items;
    return items.filter(item => item.deal_grade === grade);
  }, [items, grade]);

  const paginatedItems = useMemo(() => {
    return filteredItems.slice(0, visibleCount);
  }, [filteredItems, visibleCount]);

  const hasMore = filteredItems.length > visibleCount;

  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (grade) count++;
    if (brand) count++;
    if (category) count++;
    if (minPrice !== '' || maxPrice !== '') count++;
    if (season) count++;
    if (yearMin !== '' || yearMax !== '') count++;
    if (needsReview) count++;
    return count;
  }, [grade, brand, category, minPrice, maxPrice, season, yearMin, yearMax, needsReview]);

  const handleClearFilters = useCallback(() => {
    setSearchParams({}, { replace: true });
    setVisibleCount(PAGE_SIZE);
  }, [setSearchParams]);

  const activeFilters = useMemo(() => {
    const filters: { label: string; onRemove: () => void }[] = [];
    if (grade) filters.push({ label: `Grade ${grade}`, onRemove: () => setGrade(null) });
    if (brand) filters.push({ label: brand, onRemove: () => setBrand('') });
    if (category) filters.push({ label: category, onRemove: () => setCategory('') });
    if (minPrice !== '' || maxPrice !== '') {
      const label = minPrice !== '' && maxPrice !== ''
        ? `$${minPrice}–$${maxPrice}`
        : minPrice !== '' ? `$${minPrice}+` : `≤$${maxPrice}`;
      filters.push({ label, onRemove: () => { setMinPrice(''); setMaxPrice(''); } });
    }
    if (season) filters.push({ label: season, onRemove: () => setSeason('') });
    if (yearMin !== '' || yearMax !== '') {
      const label = yearMin !== '' && yearMax !== ''
        ? `${yearMin}–${yearMax}`
        : yearMin !== '' ? `${yearMin}+` : `≤${yearMax}`;
      filters.push({ label, onRemove: () => { setYearMin(''); setYearMax(''); } });
    }
    if (needsReview) filters.push({
      label: 'Needs Review',
      onRemove: () => setParam('needs_review', null),
    });
    return filters;
  }, [grade, brand, category, minPrice, maxPrice, season, yearMin, yearMax, needsReview, setGrade, setBrand, setCategory, setMinPrice, setMaxPrice, setSeason, setYearMin, setYearMax, setParam]);

  return (
    <div className="min-h-screen bg-void">
      {/* Mobile Header */}
      <div className="lg:hidden sticky top-12 z-30 surface-glass px-4 py-2.5">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs text-text-secondary">{filteredItems.length} deals</span>
          <button
            onClick={() => setSidebarOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1 bg-surface rounded border border-border font-mono text-[10px] text-text-secondary"
          >
            <SlidersHorizontal className="w-3 h-3" />
            Filters
            {activeFiltersCount > 0 && (
              <span className="w-4 h-4 rounded-full bg-accent text-void text-[9px] flex items-center justify-center font-medium">
                {activeFiltersCount}
              </span>
            )}
          </button>
        </div>
      </div>

      <div className="flex">
        {/* Sidebar - Desktop */}
        <div className="hidden lg:block">
          <FilterSidebar
            isOpen={true}
            onClose={() => setSidebarOpen(false)}
            grade={grade} onGradeChange={setGrade}
            brand={brand} onBrandChange={setBrand}
            category={category} onCategoryChange={setCategory}
            minPrice={minPrice} maxPrice={maxPrice}
            onMinPriceChange={setMinPrice} onMaxPriceChange={setMaxPrice}
            season={season} onSeasonChange={setSeason}
            yearMin={yearMin} yearMax={yearMax}
            onYearMinChange={setYearMin} onYearMaxChange={setYearMax}
            needsReview={needsReview}
            onNeedsReviewChange={(v) => setParam('needs_review', v ? '1' : null)}
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
              grade={grade} onGradeChange={setGrade}
              brand={brand} onBrandChange={setBrand}
              category={category} onCategoryChange={setCategory}
              minPrice={minPrice} maxPrice={maxPrice}
              onMinPriceChange={setMinPrice} onMaxPriceChange={setMaxPrice}
              season={season} onSeasonChange={setSeason}
              yearMin={yearMin} yearMax={yearMax}
              onYearMinChange={setYearMin} onYearMaxChange={setYearMax}
              needsReview={needsReview}
              onNeedsReviewChange={(v) => setParam('needs_review', v ? '1' : null)}
              activeFiltersCount={activeFiltersCount}
              onClearFilters={handleClearFilters}
            />
          )}
        </AnimatePresence>

        {/* Main Content */}
        <main className="flex-1 min-w-0">
          {/* Desktop Header */}
          <div className="hidden lg:block sticky top-0 z-20 surface-glass px-5 py-3">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h1 className="font-serif text-headline text-text-primary italic">Deals</h1>
                <p className="font-mono text-[10px] text-text-muted mt-0.5 tracking-wide">
                  {isLoading ? 'SCANNING...' : `${filteredItems.length} OPPORTUNITIES`}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <SortTabs value={sort} onChange={setSort} />

                <div className="flex items-center bg-surface rounded-lg p-0.5 border border-border">
                  <button
                    onClick={() => setView('grid')}
                    className={`p-1.5 rounded transition-colors ${
                      view === 'grid' ? 'bg-surface-hover text-text-primary' : 'text-text-muted hover:text-text-secondary'
                    }`}
                  >
                    <Grid3X3 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => setView('list')}
                    className={`p-1.5 rounded transition-colors ${
                      view === 'list' ? 'bg-surface-hover text-text-primary' : 'text-text-muted hover:text-text-secondary'
                    }`}
                  >
                    <List className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>

            {/* Active Filters */}
            {activeFilters.length > 0 && (
              <div className="flex items-center gap-1.5 mt-2.5 flex-wrap">
                <span className="font-mono text-[9px] text-text-muted uppercase tracking-wider">Active:</span>
                {activeFilters.map((filter, index) => (
                  <span
                    key={index}
                    className="inline-flex items-center gap-1 px-2 py-0.5 bg-accent/5 border border-accent/10 rounded font-mono text-[10px] text-accent"
                  >
                    {filter.label}
                    <button onClick={filter.onRemove} className="hover:text-text-primary transition-colors">
                      <X className="w-2.5 h-2.5" />
                    </button>
                  </span>
                ))}
                <button
                  onClick={handleClearFilters}
                  className="font-mono text-[10px] text-text-muted hover:text-signal-red transition-colors ml-1"
                >
                  Reset
                </button>
              </div>
            )}
          </div>

          {/* Mobile Sort Bar */}
          <div className="lg:hidden px-4 py-2.5 border-b border-border">
            <SortTabs value={sort} onChange={setSort} />
          </div>

          {/* Recent scrape runs */}
          {historyData?.runs && historyData.runs.length > 0 && (
            <div className="px-4 lg:px-5 pt-4 lg:pt-5">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-3 h-3 text-text-muted" />
                <span className="font-mono text-[10px] text-text-muted uppercase tracking-wider">Recent Scrapes</span>
              </div>
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                {historyData.runs.slice(0, 5).map((run) => (
                  <div
                    key={run.run_id}
                    className="flex-shrink-0 flex items-center gap-2 px-2.5 py-1.5 bg-surface rounded border border-border font-mono text-[10px]"
                  >
                    <div className={`w-1.5 h-1.5 rounded-full ${
                      run.status === 'completed' ? 'bg-signal-green' :
                      run.status === 'running' ? 'bg-signal-amber animate-pulse-slow' :
                      run.status === 'failed' ? 'bg-signal-red' : 'bg-text-muted'
                    }`} />
                    <span className="text-text-secondary">
                      {run.mode === 'gap_hunter' ? 'Gap' : 'Full'}
                    </span>
                    <span className="text-text-muted">
                      {new Date(run.started_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </span>
                    {run.stats?.deals_found != null && (
                      <span className="text-signal-green">{run.stats.deals_found} deals</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Results */}
          <div className="p-4 lg:p-5">
            {isLoading ? (
              <SkeletonGrid count={8} view={view} />
            ) : filteredItems.length === 0 ? (
              <EmptyDeals onClearFilters={handleClearFilters} />
            ) : (
              <>
                <div className={`grid gap-3 ${
                  view === 'grid'
                    ? 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4'
                    : 'grid-cols-1 max-w-4xl'
                }`}>
                  {paginatedItems.map((item) => (
                    <DealCard key={item.id} item={item} view={view} onClick={setSelectedItem} />
                  ))}
                </div>

                {hasMore && (
                  <div className="flex items-center justify-center mt-6">
                    <button
                      onClick={handleLoadMore}
                      className="flex items-center gap-2 px-5 py-2.5 bg-surface hover:bg-surface-hover border border-border hover:border-border-strong rounded font-mono text-[11px] text-text-secondary hover:text-text-primary uppercase tracking-wider transition-all"
                    >
                      <ChevronDown className="w-3.5 h-3.5" />
                      Load More
                      <span className="text-text-muted">
                        ({paginatedItems.length} of {filteredItems.length})
                      </span>
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </main>
      </div>
      {/* Item Detail Panel */}
      <AnimatePresence>
        {selectedItem && (
          <ItemDetailPanel item={selectedItem} onClose={() => setSelectedItem(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}
