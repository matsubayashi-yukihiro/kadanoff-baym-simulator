export function Chip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
        active
          ? "bg-accent text-white"
          : "bg-panel-strong text-ink-subtle hover:bg-accent-soft/30 hover:text-ink"
      }`}
    >
      {label}
    </button>
  );
}
