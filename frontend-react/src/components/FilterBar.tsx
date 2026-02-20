import type { Grade, SortField, ViewMode } from '../types';
import { Grid3X3, List, Filter } from 'lucide-react';

interface FilterBarProps {
  grade: Grade;
  onGradeChange: (grade: Grade) => void;
  brand: string;
  onBrandChange: (brand: string) => void;
  sort: SortField;
  onSortChange: (sort: SortField) => void;
  view: ViewMode;
  onViewChange: (view: ViewMode) => void;
}

export function FilterBar({
  grade,
  onGradeChange,
  sort,
  onSortChange,
  view,
  onViewChange,
}: FilterBarProps) {
  const grades: { value: Grade; label: string; color: string }[] = [
    { value: null, label: 'All', color: 'bg-gray-700' },
    { value: 'A', label: 'A', color: 'bg-green-600' },
    { value: 'B', label: 'B', color: 'bg-blue-600' },
    { value: 'C', label: 'C', color: 'bg-yellow-600' },
  ];

  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-800 mb-6">
      <div className="flex flex-wrap items-center gap-4">
        {/* Grade Filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <span className="text-sm text-gray-400">Grade:</span>
          <div className="flex gap-1">
            {grades.map((g) => (
              <button
                key={g.label}
                onClick={() => onGradeChange(g.value)}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  grade === g.value
                    ? `${g.color} text-white`
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {g.label}
              </button>
            ))}
          </div>
        </div>

        {/* Sort */}
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-sm text-gray-400">Sort:</span>
          <select
            value={sort}
            onChange={(e) => onSortChange(e.target.value as SortField)}
            className="bg-gray-800 text-white text-sm rounded-lg px-3 py-1.5 border border-gray-700"
          >
            <option value="profit">Profit</option>
            <option value="margin">Margin</option>
            <option value="grade">Grade</option>
            <option value="newest">Newest</option>
          </select>
        </div>

        {/* View Toggle */}
        <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
          <button
            onClick={() => onViewChange('grid')}
            className={`p-1.5 rounded transition-colors ${
              view === 'grid' ? 'bg-gray-700 text-white' : 'text-gray-400'
            }`}
          >
            <Grid3X3 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onViewChange('list')}
            className={`p-1.5 rounded transition-colors ${
              view === 'list' ? 'bg-gray-700 text-white' : 'text-gray-400'
            }`}
          >
            <List className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
