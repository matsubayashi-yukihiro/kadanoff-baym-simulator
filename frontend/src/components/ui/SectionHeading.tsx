export function SectionHeading({
  eyebrow,
  title,
  copy,
}: {
  eyebrow: string;
  title: string;
  copy?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-6 mb-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-ink-muted mb-1">
          {eyebrow}
        </p>
        <h2 className="font-heading text-xl font-semibold text-ink leading-snug">{title}</h2>
      </div>
      {copy ? (
        <p className="text-sm text-ink-muted max-w-md shrink-0">{copy}</p>
      ) : null}
    </div>
  );
}
