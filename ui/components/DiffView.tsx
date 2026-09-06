export function DiffView({ diff }: { diff: string }) {
  return (
    <pre className="overflow-x-auto rounded border border-border bg-bg p-4 font-mono text-xs leading-relaxed">
      {diff.split("\n").map((line, index) => {
        const added = line.startsWith("+") && !line.startsWith("+++");
        const removed = line.startsWith("-") && !line.startsWith("---");
        const meta = line.startsWith("@@");
        return (
          <div
            key={index}
            className={
              added
                ? "text-pass"
                : removed
                  ? "text-fail"
                  : meta
                    ? "text-accent"
                    : "text-muted"
            }
          >
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}
