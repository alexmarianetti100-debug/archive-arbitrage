import { motion } from 'framer-motion';

interface SkeletonCardProps {
  view?: 'grid' | 'list';
}

export function SkeletonCard({ view = 'grid' }: SkeletonCardProps) {
  if (view === 'list') {
    return (
      <div className="bg-surface rounded-lg border border-border p-3 animate-pulse">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded bg-surface-hover flex-shrink-0" />
          <div className="flex-1 space-y-1.5">
            <div className="flex items-center gap-2">
              <div className="w-6 h-4 rounded bg-surface-hover" />
              <div className="w-16 h-3 rounded bg-surface-hover" />
            </div>
            <div className="w-3/4 h-3 rounded bg-surface-hover" />
          </div>
          <div className="w-16 h-6 rounded bg-surface-hover" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface rounded-lg border border-border overflow-hidden animate-pulse">
      <div className="aspect-[4/3] bg-surface-hover" />
      <div className="p-3.5 space-y-2.5">
        <div className="w-20 h-2.5 rounded bg-surface-hover" />
        <div className="space-y-1">
          <div className="w-full h-3 rounded bg-surface-hover" />
          <div className="w-2/3 h-3 rounded bg-surface-hover" />
        </div>
        <div className="flex items-baseline gap-2 pt-1">
          <div className="w-14 h-5 rounded bg-surface-hover" />
          <div className="w-10 h-3 rounded bg-surface-hover" />
        </div>
        <div className="flex items-center justify-between">
          <div className="w-16 h-4 rounded bg-surface-hover" />
          <div className="w-12 h-3 rounded bg-surface-hover" />
        </div>
        <div className="w-full h-8 rounded bg-surface-hover mt-1" />
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
    <div className={`grid gap-3 ${
      view === 'grid'
        ? 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4'
        : 'grid-cols-1'
    }`}>
      {[...Array(count)].map((_, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.04 }}
        >
          <SkeletonCard view={view} />
        </motion.div>
      ))}
    </div>
  );
}
