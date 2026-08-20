import type { Group } from "../lib/api";
import { LinkCard } from "./LinkCard";

export function GroupSection({ group }: { group: Group }) {
  if (group.links.length === 0) {
    return null;
  }
  return (
    <section className="mb-8">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-muted">
        <svg className="h-4 w-4" aria-hidden="true"><use href="/icons.svg#i-grid" /></svg>
        {group.name}
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {group.links.map((link) => (
          <LinkCard key={link.id} link={link} />
        ))}
      </div>
    </section>
  );
}
