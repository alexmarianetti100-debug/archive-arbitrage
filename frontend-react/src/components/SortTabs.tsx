import { motion } from 'framer-motion';
import type { SortField } from '../types';

interface SortTabsProps {
  value: SortField;
  onChange: (sort: SortField) => void;
}

const sortOptions: { value: SortField; label: string }[] = [
  { value: 'profit', label: 'Profit' },
  { value: 'margin', label: 'Margin' },
  { value: 'grade', label: 'Grade' },
  { value: 'newest', label: 'Newest' },
];

export function SortTabs({ value, onChange }: SortTabsProps) {
  return (
    <div className="flex items-center gap-1 bg-surface rounded-lg p-1">
      <span className="text-xs text-text-secondary px-2">Sort:</span>
      {sortOptions.map((option) => {
        const isActive = value === option.value;
        
        return (
          <button
            key={option.value}
            onClick={() => onChange(option.value)}
            className={`relative px-3 py-1.5 text-sm font-medium rounded-md transition-all duration-200 ${
              isActive
                ? 'text-white'
                : 'text-text-secondary hover:text-text-primary hover:bg-surface-hover'
            }`}
          >
            {isActive && (
              <motion.div
                layoutId="sortActive"
                className="absolute inset-0 bg-accent rounded-md"
                transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }}
              />
            )}
            <span className="relative z-10">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
