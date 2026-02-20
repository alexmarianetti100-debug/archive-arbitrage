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
        className="w-full flex items-center justify-between py-3 px-1 text-sm font-medium text-text-primary hover:text-white transition-colors"
      >
        {title}
        <ChevronDown 
          className={`w-4 h-4 text-text-secondary transition-transform duration-200 ${
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
            <div className="pb-4">
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

  return (
    <>
      {/* Mobile overlay */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
      />
      
      {/* Sidebar */}
      <motion.aside
        initial={{ x: '-100%' }}
        animate={{ x: 0 }}
        exit={{ x: '-100%' }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className="fixed left-0 top-0 h-full w-80 bg-surface border-r border-border z-50 lg:static lg:z-auto flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border flex-shrink-0">
          <div>
            <h2 className="font-semibold text-text-primary">Filters</h2>
            {activeFiltersCount > 0 && (
              <p className="text-xs text-text-secondary">
                {activeFiltersCount} active
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {activeFiltersCount > 0 && (
              <button
                onClick={onClearFilters}
                className="text-xs text-accent hover:text-accent-light transition-colors"
              >
                Clear all
              </button>
            )}
            <button
              onClick={onClose}
              className="p-2 hover:bg-surface-hover rounded-lg transition-colors lg:hidden"
            >
              <X className="w-5 h-5 text-text-secondary" />
            </button>
          </div>
        </div>

        {/* Filter sections - scrollable */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {/* Grade Filter */}
          <AccordionSection title="Deal Grade" defaultOpen={true}>
            <div className="space-y-1.5">
              {grades.map((g) => (
                <button
                  key={g.value}
                  onClick={() => onGradeChange(grade === g.value ? null : g.value)}
                  className={`w-full flex items-center gap-3 p-2.5 rounded-lg transition-all ${
                    grade === g.value
                      ? 'bg-surface-hover border border-accent/30'
                      : 'hover:bg-surface-hover'
                  }`}
                >
                  <span className={`w-6 h-6 rounded flex items-center justify-center text-xs font-bold text-white ${g.color}`}>
                    {g.label}
                  </span>
                  <div className="text-left">
                    <span className="text-sm text-text-primary">Grade {g.label}</span>
                    <p className="text-2xs text-text-muted">{g.description}</p>
                  </div>
                  {grade === g.value && (
                    <motion.div
                      layoutId="gradeCheck"
                      className="ml-auto w-2 h-2 rounded-full bg-accent"
                    />
                  )}
                </button>
              ))}
            </div>
          </AccordionSection>

          {/* Brand Filter */}
          <AccordionSection title="Brand" defaultOpen={false}>
            <div className="space-y-3">
              {/* Brand Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="text"
                  placeholder="Search brands..."
                  value={brandSearch}
                  onChange={(e) => setBrandSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
                />
              </div>
              
              {/* Selected Brand */}
              {brand && (
                <div className="flex items-center gap-2 p-2 bg-accent/10 border border-accent/20 rounded-lg">
                  <span className="text-sm text-text-primary flex-1">{brand}</span>
                  <button
                    onClick={() => onBrandChange('')}
                    className="p-1 hover:bg-accent/20 rounded transition-colors"
                  >
                    <X className="w-4 h-4 text-text-secondary" />
                  </button>
                </div>
              )}
              
              {/* Brand List */}
              <div className="max-h-48 overflow-y-auto space-y-1">
                {isLoadingBrands ? (
                  <div className="text-sm text-text-secondary py-2">Loading brands...</div>
                ) : filteredBrands.length === 0 ? (
                  <div className="text-sm text-text-secondary py-2">No brands found</div>
                ) : (
                  filteredBrands.slice(0, 20).map((b) => (
                    <button
                      key={b}
                      onClick={() => onBrandChange(b === brand ? '' : b)}
                      className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                        brand === b
                          ? 'bg-accent/20 text-accent'
                          : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
                      }`}
                    >
                      {b}
                    </button>
                  ))
                )}
                {filteredBrands.length > 20 && (
                  <p className="text-xs text-text-muted px-3 py-1">
                    +{filteredBrands.length - 20} more brands
                  </p>
                )}
              </div>
            </div>
          </AccordionSection>

          {/* Category Filter */}
          <AccordionSection title="Category" defaultOpen={false}>
            <div className="space-y-1">
              {categories.map((c) => (
                <button
                  key={c.value}
                  onClick={() => onCategoryChange(c.value === category ? '' : c.value)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    category === c.value
                      ? 'bg-accent/20 text-accent'
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
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                  <input
                    type="number"
                    placeholder="Min"
                    value={minPrice}
                    onChange={(e) => onMinPriceChange(e.target.value ? Number(e.target.value) : '')}
                    className="w-full pl-8 pr-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
                  />
                </div>
                <span className="text-text-muted">-</span>
                <div className="relative flex-1">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                  <input
                    type="number"
                    placeholder="Max"
                    value={maxPrice}
                    onChange={(e) => onMaxPriceChange(e.target.value ? Number(e.target.value) : '')}
                    className="w-full pl-8 pr-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
                  />
                </div>
              </div>
              {(minPrice !== '' || maxPrice !== '') && (
                <button
                  onClick={() => {
                    onMinPriceChange('');
                    onMaxPriceChange('');
                  }}
                  className="text-xs text-accent hover:text-accent-light transition-colors"
                >
                  Clear price filter
                </button>
              )}
            </div>
          </AccordionSection>

          {/* Season Filter */}
          <AccordionSection title="Season" defaultOpen={false}>
            <div className="space-y-1">
              {seasons.map((s) => (
                <button
                  key={s.value}
                  onClick={() => onSeasonChange(s.value === season ? '' : s.value)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    season === s.value
                      ? 'bg-accent/20 text-accent'
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
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                  <input
                    type="number"
                    placeholder="From"
                    min="1990"
                    max="2030"
                    value={yearMin}
                    onChange={(e) => onYearMinChange(e.target.value ? Number(e.target.value) : '')}
                    className="w-full pl-8 pr-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
                  />
                </div>
                <span className="text-text-muted">-</span>
                <div className="relative flex-1">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                  <input
                    type="number"
                    placeholder="To"
                    min="1990"
                    max="2030"
                    value={yearMax}
                    onChange={(e) => onYearMaxChange(e.target.value ? Number(e.target.value) : '')}
                    className="w-full pl-8 pr-3 py-2 bg-background border border-border rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent"
                  />
                </div>
              </div>
              {(yearMin !== '' || yearMax !== '') && (
                <button
                  onClick={() => {
                    onYearMinChange('');
                    onYearMaxChange('');
                  }}
                  className="text-xs text-accent hover:text-accent-light transition-colors"
                >
                  Clear year filter
                </button>
              )}
            </div>
          </AccordionSection>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border bg-surface flex-shrink-0">
          <button
            onClick={onClose}
            className="w-full py-2.5 bg-accent hover:bg-accent-hover text-white font-medium rounded-lg transition-colors"
          >
            Show Results
          </button>
        </div>
      </motion.aside>
    </>
  );
}
