import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, X, Search, DollarSign, Calendar } from 'lucide-react';
import type { Grade } from '../types';
import { fetchBrands } from '../utils/api';

interface FilterSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  grade: Grade;
  onGradeChange: (grade: Grade) => void;
  brand: string;
  onBrandChange: (brand: string) => void;
  category: string;
  onCategoryChange: (category: string) => void;
  minPrice: number | '';
  maxPrice: number | '';
  onMinPriceChange: (price: number | '') => void;
  onMaxPriceChange: (price: number | '') => void;
  season: string;
  onSeasonChange: (season: string) => void;
  yearMin: number | '';
  yearMax: number | '';
  onYearMinChange: (year: number | '') => void;
  onYearMaxChange: (year: number | '') => void;
  needsReview: boolean;
  onNeedsReviewChange: (value: boolean) => void;
  activeFiltersCount: number;
  onClearFilters: () => void;
}

const grades: { value: Grade; label: string; color: string; description: string }[] = [
  { value: 'A', label: 'A', color: 'bg-grade-a', description: 'Guaranteed flip' },
  { value: 'B', label: 'B', color: 'bg-grade-b', description: 'Likely flip' },
  { value: 'C', label: 'C', color: 'bg-grade-c', description: 'Possible flip' },
  { value: 'D', label: 'D', color: 'bg-grade-d', description: 'Skip' },
];

const seasons = [
  { value: '', label: 'All Seasons' },
  { value: 'FW', label: 'Fall/Winter' },
  { value: 'SS', label: 'Spring/Summer' },
  { value: 'AW', label: 'Autumn/Winter' },
  { value: 'RESORT', label: 'Resort' },
  { value: 'CRUISE', label: 'Cruise' },
  { value: 'PF', label: 'Pre-Fall' },
];

const categories = [
  { value: '', label: 'All Categories' },
  { value: 'outerwear', label: 'Outerwear' },
  { value: 'footwear', label: 'Footwear' },
  { value: 'tops', label: 'Tops' },
  { value: 'bottoms', label: 'Bottoms' },
  { value: 'accessories', label: 'Accessories' },
];

interface AccordionSectionProps {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function AccordionSection({ title, children, defaultOpen = false }: AccordionSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-border last:border-0">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between py-2.5 px-1 font-mono text-[10px] uppercase tracking-[0.12em] text-text-secondary hover:text-text-primary transition-colors"
      >
        {title}
        <ChevronDown
          className={`w-3 h-3 text-text-muted transition-transform duration-200 ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </button>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="pb-3">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function FilterSidebar({
  isOpen,
  onClose,
  grade,
  onGradeChange,
  brand,
  onBrandChange,
  category,
  onCategoryChange,
  minPrice,
  maxPrice,
  onMinPriceChange,
  onMaxPriceChange,
  season,
  onSeasonChange,
  yearMin,
  yearMax,
  onYearMinChange,
  onYearMaxChange,
  needsReview,
  onNeedsReviewChange,
  activeFiltersCount,
  onClearFilters,
}: FilterSidebarProps) {
  const [brands, setBrands] = useState<string[]>([]);
  const [brandSearch, setBrandSearch] = useState('');
  const [isLoadingBrands, setIsLoadingBrands] = useState(false);

  useEffect(() => {
    const loadBrands = async () => {
      setIsLoadingBrands(true);
      try {
        const data = await fetchBrands();
        setBrands(data);
      } catch (err) {
        console.error('Failed to load brands:', err);
      } finally {
        setIsLoadingBrands(false);
      }
    };

    if (isOpen) {
      loadBrands();
    }
  }, [isOpen]);

  const filteredBrands = brands.filter(b =>
    b.toLowerCase().includes(brandSearch.toLowerCase())
  );

  if (!isOpen) return null;

  const inputClass = "w-full pl-7 pr-3 py-1.5 bg-void border border-border rounded font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/40";

  return (
    <>
      {/* Mobile overlay */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 bg-black/80 backdrop-blur-sm z-40 lg:hidden"
      />

      {/* Sidebar */}
      <motion.aside
        initial={{ x: '-100%' }}
        animate={{ x: 0 }}
        exit={{ x: '-100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 300 }}
        className="fixed left-0 top-0 h-full w-72 bg-surface border-r border-border z-50 lg:static lg:z-auto flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b border-border flex-shrink-0">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-text-secondary">Filters</span>
            {activeFiltersCount > 0 && (
              <span className="font-mono text-[10px] text-accent ml-2">{activeFiltersCount}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {activeFiltersCount > 0 && (
              <button
                onClick={onClearFilters}
                className="font-mono text-[10px] text-signal-red hover:text-signal-red/80 transition-colors"
              >
                Reset
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-surface-hover rounded transition-colors lg:hidden"
            >
              <X className="w-3.5 h-3.5 text-text-muted" />
            </button>
          </div>
        </div>

        {/* Review Status */}
        <div className="px-4 py-3 border-b border-border">
          <button
            onClick={() => onNeedsReviewChange(!needsReview)}
            className={`w-full flex items-center justify-between px-3 py-2 rounded border transition-colors ${
              needsReview
                ? 'border-signal-amber/30 bg-signal-amber/10 text-signal-amber'
                : 'border-border bg-surface text-text-muted hover:text-text-secondary'
            }`}
          >
            <span className="font-mono text-[10px] uppercase tracking-wider">Needs Review</span>
            {needsReview && <span className="font-mono text-[10px]">ON</span>}
          </button>
        </div>

        {/* Filter sections */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {/* Grade Filter */}
          <AccordionSection title="Deal Grade" defaultOpen={true}>
            <div className="space-y-1">
              {grades.map((g) => (
                <button
                  key={g.value}
                  onClick={() => onGradeChange(grade === g.value ? null : g.value)}
                  className={`w-full flex items-center gap-2.5 p-2 rounded transition-all ${
                    grade === g.value
                      ? 'bg-surface-hover border border-accent/15'
                      : 'hover:bg-surface-hover border border-transparent'
                  }`}
                >
                  <span className={`grade-badge rounded ${
                    g.value === 'A' ? 'grade-a' :
                    g.value === 'B' ? 'grade-b' :
                    g.value === 'C' ? 'grade-c' : 'grade-d'
                  }`}>
                    {g.label}
                  </span>
                  <div className="text-left">
                    <span className="text-xs text-text-primary">Grade {g.label}</span>
                    <p className="font-mono text-[9px] text-text-muted">{g.description}</p>
                  </div>
                  {grade === g.value && (
                    <motion.div
                      layoutId="gradeCheck"
                      className="ml-auto w-1.5 h-1.5 rounded-full bg-accent"
                    />
                  )}
                </button>
              ))}
            </div>
          </AccordionSection>

          {/* Brand Filter */}
          <AccordionSection title="Brand" defaultOpen={false}>
            <div className="space-y-2">
              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
                <input
                  type="text"
                  placeholder="Search..."
                  value={brandSearch}
                  onChange={(e) => setBrandSearch(e.target.value)}
                  className={inputClass}
                />
              </div>

              {brand && (
                <div className="flex items-center gap-2 p-1.5 bg-accent/5 border border-accent/10 rounded">
                  <span className="font-mono text-[11px] text-text-primary flex-1">{brand}</span>
                  <button
                    onClick={() => onBrandChange('')}
                    className="p-0.5 hover:bg-accent/10 rounded transition-colors"
                  >
                    <X className="w-3 h-3 text-text-muted" />
                  </button>
                </div>
              )}

              <div className="max-h-40 overflow-y-auto space-y-0.5">
                {isLoadingBrands ? (
                  <span className="font-mono text-[10px] text-text-muted py-2 block">Loading...</span>
                ) : filteredBrands.length === 0 ? (
                  <span className="font-mono text-[10px] text-text-muted py-2 block">No brands found</span>
                ) : (
                  filteredBrands.slice(0, 20).map((b) => (
                    <button
                      key={b}
                      onClick={() => onBrandChange(b === brand ? '' : b)}
                      className={`w-full text-left px-2 py-1.5 rounded font-mono text-[11px] transition-colors ${
                        brand === b
                          ? 'bg-accent/10 text-accent'
                          : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                      }`}
                    >
                      {b}
                    </button>
                  ))
                )}
                {filteredBrands.length > 20 && (
                  <p className="font-mono text-[9px] text-text-muted px-2 py-1">
                    +{filteredBrands.length - 20} more
                  </p>
                )}
              </div>
            </div>
          </AccordionSection>

          {/* Category Filter */}
          <AccordionSection title="Category" defaultOpen={false}>
            <div className="space-y-0.5">
              {categories.map((c) => (
                <button
                  key={c.value}
                  onClick={() => onCategoryChange(c.value === category ? '' : c.value)}
                  className={`w-full text-left px-2 py-1.5 rounded font-mono text-[11px] transition-colors ${
                    category === c.value
                      ? 'bg-accent/10 text-accent'
                      : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </AccordionSection>

          {/* Price Range Filter */}
          <AccordionSection title="Price Range" defaultOpen={false}>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <DollarSign className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
                  <input
                    type="number"
                    placeholder="Min"
                    value={minPrice}
                    onChange={(e) => onMinPriceChange(e.target.value ? Number(e.target.value) : '')}
                    className={inputClass}
                  />
                </div>
                <span className="text-text-muted text-xs">—</span>
                <div className="relative flex-1">
                  <DollarSign className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
                  <input
                    type="number"
                    placeholder="Max"
                    value={maxPrice}
                    onChange={(e) => onMaxPriceChange(e.target.value ? Number(e.target.value) : '')}
                    className={inputClass}
                  />
                </div>
              </div>
              {(minPrice !== '' || maxPrice !== '') && (
                <button
                  onClick={() => { onMinPriceChange(''); onMaxPriceChange(''); }}
                  className="font-mono text-[10px] text-signal-red hover:text-signal-red/80 transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
          </AccordionSection>

          {/* Season Filter */}
          <AccordionSection title="Season" defaultOpen={false}>
            <div className="space-y-0.5">
              {seasons.map((s) => (
                <button
                  key={s.value}
                  onClick={() => onSeasonChange(s.value === season ? '' : s.value)}
                  className={`w-full text-left px-2 py-1.5 rounded font-mono text-[11px] transition-colors ${
                    season === s.value
                      ? 'bg-accent/10 text-accent'
                      : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </AccordionSection>

          {/* Year Filter */}
          <AccordionSection title="Year" defaultOpen={false}>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Calendar className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
                  <input
                    type="number"
                    placeholder="From"
                    min="1990"
                    max="2030"
                    value={yearMin}
                    onChange={(e) => onYearMinChange(e.target.value ? Number(e.target.value) : '')}
                    className={inputClass}
                  />
                </div>
                <span className="text-text-muted text-xs">—</span>
                <div className="relative flex-1">
                  <Calendar className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
                  <input
                    type="number"
                    placeholder="To"
                    min="1990"
                    max="2030"
                    value={yearMax}
                    onChange={(e) => onYearMaxChange(e.target.value ? Number(e.target.value) : '')}
                    className={inputClass}
                  />
                </div>
              </div>
              {(yearMin !== '' || yearMax !== '') && (
                <button
                  onClick={() => { onYearMinChange(''); onYearMaxChange(''); }}
                  className="font-mono text-[10px] text-signal-red hover:text-signal-red/80 transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
          </AccordionSection>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-border bg-surface flex-shrink-0">
          <button
            onClick={onClose}
            className="w-full py-2 bg-accent hover:bg-accent-hover text-void font-mono text-[11px] uppercase tracking-wider rounded transition-colors lg:hidden"
          >
            Show Results
          </button>
        </div>
      </motion.aside>
    </>
  );
}
