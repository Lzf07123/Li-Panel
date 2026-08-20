export function PageSkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-10 flex flex-col items-center gap-3">
        <div className="skeleton-block h-14 w-14 rounded-2xl" />
        <div className="skeleton-block h-6 w-40" />
        <div className="skeleton-block h-4 w-64" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <div key={index} className="skeleton-block h-20" />
        ))}
      </div>
    </div>
  );
}
