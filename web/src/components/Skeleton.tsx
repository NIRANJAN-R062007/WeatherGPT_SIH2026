interface LinesProps {
  kind: 'lines';
  count?: number;
}

interface StatProps {
  kind: 'stat';
}

interface BannerProps {
  kind: 'banner';
}

type Props = LinesProps | StatProps | BannerProps;

/** Skeleton shapes matching the content each page will replace them with. */
export function Skeleton(props: Props) {
  if (props.kind === 'lines') {
    const count = props.count ?? 3;
    return (
      <div className="animate-pulse space-y-3" aria-hidden>
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="h-4 rounded-sm bg-paper-dim" style={{ width: `${90 - i * 12}%` }} />
        ))}
      </div>
    );
  }

  if (props.kind === 'stat') {
    return (
      <div className="grid animate-pulse grid-cols-2 gap-px bg-line md:grid-cols-4" aria-hidden>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-2 bg-paper p-4">
            <div className="h-3 w-16 rounded-sm bg-paper-dim" />
            <div className="h-6 w-12 rounded-sm bg-paper-dim" />
          </div>
        ))}
      </div>
    );
  }

  return <div className="h-32 animate-pulse rounded-sm border border-line bg-paper-dim" aria-hidden />;
}
