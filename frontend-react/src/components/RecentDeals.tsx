import { useItems } from '../hooks/useApi';
import { DealCard } from './DealCard';

export function RecentDeals() {
  const { data: items } = useItems({ sort: 'grade_asc', page_size: 4 });

  if (!items?.length) {
    return (
      <div className="text-center py-8">
        <span className="font-mono text-[11px] text-text-muted">No recent deals in pipeline</span>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
      {items.map(item => (
        <DealCard key={item.id} item={item} view="grid" />
      ))}
    </div>
  );
}
