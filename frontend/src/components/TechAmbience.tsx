export function TechAmbience() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
    >
      <div className="tech-grid absolute inset-0" />
      <div className="tech-beam" />
      <div className="tech-beam" />
      <div className="tech-beam" />
      {Array.from({ length: 8 }).map((_, index) => (
        <div key={index} className="tech-dot" />
      ))}
    </div>
  );
}
