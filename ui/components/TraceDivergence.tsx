"use client";

import { motion, useReducedMotion } from "framer-motion";

import { motionTokens } from "@/lib/motion";
import type { LaneSpan, TraceLane } from "@/lib/types";

// Spans in these traces last microseconds while a run lasts a millisecond, so
// drawing each span as a width-proportional block makes every block the same
// invisible sliver. What actually matters — and what the harness controls — is
// the *start order*, so each operation is drawn as a labelled marker anchored at
// its true start time, on an axis shared between the two runs.

const ROW_HEIGHT = 30;
const CHAR_WIDTH = 6.6;
const PILL_PADDING = 26;

interface Placed {
  span: LaneSpan | null;
  ghostName?: string;
  leftPct: number;
  row: number;
  anchorRight: boolean;
}

function estimateWidthPct(label: string, laneWidth: number): number {
  return ((label.length * CHAR_WIDTH + PILL_PADDING) / laneWidth) * 100;
}

function place(spans: LaneSpan[], ghosts: string[], scale: number, laneWidth: number): Placed[] {
  const placed: Placed[] = [];
  const rowEnds: number[] = [];
  for (const span of spans) {
    const leftPct = Math.min((span.start_ms / scale) * 100, 99);
    const widthPct = estimateWidthPct(span.name, laneWidth);
    const anchorRight = leftPct + widthPct > 100;
    const start = anchorRight ? leftPct - widthPct : leftPct;
    let row = rowEnds.findIndex((end) => start > end + 1);
    if (row === -1) {
      row = rowEnds.length;
      rowEnds.push(0);
    }
    rowEnds[row] = start + widthPct;
    placed.push({ span, leftPct, row, anchorRight });
  }
  // Operations the other run performed but this one never reached. Their absence
  // is the evidence, so it is drawn rather than left as blank space.
  for (const name of ghosts) {
    const row = rowEnds.length;
    rowEnds.push(100);
    placed.push({ span: null, ghostName: name, leftPct: 99.5, row, anchorRight: true });
  }
  return placed;
}

function Pill({
  item,
  index,
  laneIndex,
  animate,
}: {
  item: Placed;
  index: number;
  laneIndex: number;
  animate: boolean;
}) {
  const label = item.span?.name ?? item.ghostName ?? "";
  const highlighted = item.span?.in_inversion ?? true;
  const ghost = item.span === null;
  const classes = ghost
    ? "border-2 border-dashed border-fail/70 bg-transparent text-fail"
    : highlighted
      ? "border-2 border-warn bg-warn/15 text-warn"
      : item.span?.is_assertion
        ? "border border-border bg-bg text-muted"
        : "border border-border bg-bg text-text";
  return (
    <motion.div
      initial={animate ? { opacity: 0, x: -6 } : false}
      animate={{ opacity: 1, x: 0 }}
      transition={{
        duration: motionTokens.fast,
        ease: motionTokens.ease,
        delay: animate ? laneIndex * 0.08 + index * motionTokens.stagger : 0,
      }}
      className={`absolute flex items-center whitespace-nowrap rounded px-2 font-mono text-[11px] ${classes}`}
      // Anchored with `right` rather than a transform: framer-motion animates
      // `transform`, and would overwrite a translate used for layout.
      style={{
        ...(item.anchorRight
          ? { right: `${100 - item.leftPct}%` }
          : { left: `${item.leftPct}%` }),
        top: item.row * ROW_HEIGHT + 4,
        height: ROW_HEIGHT - 8,
      }}
      title={
        ghost
          ? `${label} never started in this run`
          : `${label} · starts at ${item.span?.start_ms.toFixed(3)} ms · ${
              item.span?.task_name ?? "task"
            } · line ${item.span?.source_line ?? "?"}${
              item.span?.access ? ` · ${item.span.access}` : ""
            }`
      }
    >
      {ghost ? `${label} — never ran` : label}
    </motion.div>
  );
}

function Lane({
  lane,
  scale,
  ghosts,
  laneIndex,
  animate,
  laneWidth,
}: {
  lane: TraceLane;
  scale: number;
  ghosts: string[];
  laneIndex: number;
  animate: boolean;
  laneWidth: number;
}) {
  const passing = lane.outcome === "PASS";
  const placed = place(lane.spans, ghosts, scale, laneWidth);
  const rows = Math.max(1, ...placed.map((item) => item.row + 1));
  return (
    <div className="mb-4">
      <div className="mb-2 flex items-center gap-2 text-xs">
        <span
          className={`inline-flex items-center gap-1 rounded border px-2 py-[2px] font-medium ${
            passing ? "border-pass/40 bg-pass/10 text-pass" : "border-fail/40 bg-fail/10 text-fail"
          }`}
        >
          <span aria-hidden="true">{passing ? "✓" : "✕"}</span>
          {passing ? "Passing run" : "Failing run"}
        </span>
        <span className="font-mono text-muted">
          {lane.spans.length} operations in {lane.total_ms.toFixed(2)} ms
        </span>
      </div>
      <div
        className="relative rounded border border-border bg-bg"
        style={{ height: rows * ROW_HEIGHT + 8 }}
      >
        {placed.map((item, index) => (
          <Pill
            key={item.span?.key ?? `ghost-${item.ghostName}`}
            item={item}
            index={index}
            laneIndex={laneIndex}
            animate={animate}
          />
        ))}
      </div>
    </div>
  );
}

export function TraceDivergence({
  passLane,
  failLane,
  inverted,
}: {
  passLane: TraceLane | null;
  failLane: TraceLane | null;
  inverted: string[];
}) {
  const reduced = useReducedMotion();
  if (!passLane || !failLane) {
    return <p className="text-sm text-muted">No paired execution was captured for this incident.</p>;
  }
  const scale = Math.max(passLane.total_ms, failLane.total_ms, 0.001);
  const laneWidth = 820;
  const passKeys = new Set(passLane.spans.map((span) => span.name));
  const failKeys = new Set(failLane.spans.map((span) => span.name));
  const missingFromFail = [...passKeys].filter((name) => !failKeys.has(name));
  const missingFromPass = [...failKeys].filter((name) => !passKeys.has(name));
  const [first, second] = inverted;

  return (
    <figure className="m-0">
      <figcaption className="sr-only">
        {`The same test twice on a shared time axis. Each operation is anchored at the moment it
        started. In the failing run ${first ?? "the reader"} starts before
        ${second ?? "the writer"}${
          missingFromFail.length
            ? `, and ${missingFromFail.join(", ")} never ran at all`
            : ""
        }.`}
      </figcaption>
      <Lane
        lane={passLane}
        scale={scale}
        ghosts={missingFromPass}
        laneIndex={0}
        animate={!reduced}
        laneWidth={laneWidth}
      />
      <Lane
        lane={failLane}
        scale={scale}
        ghosts={missingFromFail}
        laneIndex={1}
        animate={!reduced}
        laneWidth={laneWidth}
      />
      <div className="mb-4 flex justify-between font-mono text-[10px] text-muted">
        <span>0 ms</span>
        <span>{(scale / 2).toFixed(2)} ms</span>
        <span>{scale.toFixed(2)} ms</span>
      </div>
      <div className="space-y-2 text-sm text-muted">
        {inverted.length === 2 && (
          <p>
            Outlined: <span className="font-mono text-warn">{first}</span> starts before{" "}
            <span className="font-mono text-warn">{second}</span> in the failing run, and after it
            when the test passes.
          </p>
        )}
        {missingFromFail.length > 0 && (
          <p>
            <span className="font-mono text-fail">{missingFromFail.join(", ")}</span> never started
            in the failing run. The run flushed its spans normally, so that absence is evidence:
            the operation had not happened by the time the assertion read the state.
          </p>
        )}
      </div>
    </figure>
  );
}
