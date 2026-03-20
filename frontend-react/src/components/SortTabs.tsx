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
    <div className="flex items-center gap-0.5 bg-surface rounded-lg p-0.5 border border-border">
      <span className="font-mono text-[9px] text-text-muted px-2 uppercase tracking-wider">Sort</span>
      {sortOptions.map((option) => {
        const isActive = value === option.value;

        return (
          <button
            key={option.value}
            onClick={() => onChange(option.value)}
            className={`relative px-2.5 py-1.5 font-mono text-[11px] rounded transition-all ${
              isActive
                ? 'text-void'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {isActive && (
              <motion.div
                layoutId="sortActive"
                className="absolute inset-0 bg-accent rounded"
                transition={{ type: 'spring', bounce: 0.15, duration: 0.5 }}
              />
            )}
            <span className="relative z-10">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
