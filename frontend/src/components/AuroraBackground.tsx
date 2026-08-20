export function AuroraBackground({ soft = false }: { soft?: boolean }) {
  return (
    <div aria-hidden="true" className={`aurora${soft ? " aurora-soft" : ""}`}>
      <span />
      <span />
      <span />
    </div>
  );
}
