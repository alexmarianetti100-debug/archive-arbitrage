import { motion } from 'framer-motion';

interface SkeletonCardProps {
  view?: 'grid' | 'list';
}

export function SkeletonCard({ view = 'grid' }: SkeletonCardProps) {
  if (view === 'list') {
    return (
      <div className="bg-surface rounded-xl border border-border p-4 animate-pulse">
        <div className="flex items-center gap-4">
          {/* Image skeleton */}
          <div className="w-16 h-16 rounded-lg bg-surface-hover flex-shrink-0" />
          
          {/* Content skeleton */}
          <div className="flex-1 space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-8 h-5 rounded bg-surface-hover" />
              <div className="w-20 h-4 rounded bg-surface-hover" />
            </div>
            <div className="w-3/4 h-4 rounded bg-surface-hover" />
          </div>
          
          {/* Price skeleton */}
          <div className="hidden sm:block space-y-1">
            <div className="w-16 h-4 rounded bg-surface-hover" />
            <div className="w-16 h-4 rounded bg-surface-hover" />
          </div>
          
          {/* Profit skeleton */}
          <div className="w-20 h-8 rounded bg-surface-hover" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface rounded-xl border border-border overflow-hidden animate-pulse">
      {/* Image skeleton */}
      <div className="aspect-[4/3] bg-surface-hover" />
      
      {/* Content skeleton */}
      <div className="p-4 space-y-3">
        {/* Badge row */}
        <div className="flex items-center justify-between">
          <div className="w-16 h-6 rounded bg-surface-hover" />
          <div className="w-12 h-5 rounded bg-surface-hover" />
        </div>
        
        {/* Brand */}
        <div className="w-24 h-3 rounded bg-surface-hover" />
        
        {/* Title */}
        <div className="space-y-1.5">
          <div className="w-full h-4 rounded bg-surface-hover" />
          <div className="w-2/3 h-4 rounded bg-surface-hover" />
        </div>
        
        {/* Price row */}
        <div className="flex items-baseline gap-2 pt-1">
          <div className="w-16 h-6 rounded bg-surface-hover" />
          <div className="w-12 h-4 rounded bg-surface-hover" />
        </div>
        
        {/* Profit row */}
        <div className="flex items-center justify-between">
          <div className="w-20 h-5 rounded bg-surface-hover" />
          <div className="w-14 h-4 rounded bg-surface-hover" />
        </div>
        
        {/* Meta row */}
        <div className="pt-2 border-t border-border flex gap-3">
          <div className="w-20 h-3 rounded bg-surface-hover" />
          <div className="w-16 h-3 rounded bg-surface-hover" />
        </div>
        
        {/* Button skeleton */}
        <div className="w-full h-10 rounded-lg bg-surface-hover mt-2" />
      </div>
    </div>
  );
}

interface SkeletonGridProps {
  count?: number;
  view?: 'grid' | 'list';
}

export function SkeletonGrid({ count = 8, view = 'grid' }: SkeletonGridProps) {
  return (
    <div className={`grid gap-4 ${
      view === 'grid'
        ? 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4'
        : 'grid-cols-1'
    }`}>
      {[...Array(count)].map((_, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.05 }}
        >
          <SkeletonCard view={view} />
        </motion.div>
      ))}
    </div>
  );
}
