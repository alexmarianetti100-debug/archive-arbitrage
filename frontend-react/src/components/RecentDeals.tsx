import { useItems } from '../hooks/useApi';
import { DealCard } from './DealCard';

export function RecentDeals() {
  const { data: items } = useItems({ grade: 'A', limit: 4 });
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {items?.map(item => (
        <DealCard key={item.id} item={item} view="grid" />
      ))}
    </div>
  );
}
