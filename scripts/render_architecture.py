#!/usr/bin/env python3
"""Render the seven architecture stills used by the demo video's cross-fade.

`assets/architecture.html` is a self-contained Claude Design export: a bundler
shell that unpacks a template whose embedded component declares a `highlight`
enum prop (none, 1..6) plus a `dimOpacity` prop. Each still is the same page
with a different default for `highlight`, so the seven frames are pixel
identical apart from the highlighted region -- anything else drifts visibly
when they are cross-faded.

Plan A rewrites the prop default in the exported HTML. If that turns out to be
inert (the two probe renders come back identical), plan B falls back to
injecting per-variant CSS against the six region containers found in the
rendered DOM.

Usage:
    python scripts/render_architecture.py [--probe-only] [--force-plan-b]
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
import tempfile
import zlib
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "assets" / "architecture.html"
OUT_DIR = REPO_ROOT / "assets" / "video"

VIEWPORT = {"width": 1920, "height": 1080}
DEVICE_SCALE_FACTOR = 2

# highlight prop value -> output filename.
STILLS: list[tuple[str, str]] = [
    ("none", "arch-0-neutral.png"),
    ("1", "arch-1-trigger.png"),
    ("2", "arch-2-capture.png"),
    ("3", "arch-3-diagnose.png"),
    ("4", "arch-4-agent.png"),
    ("5", "arch-5-governor.png"),
    ("6", "arch-6-verify.png"),
]

# The two variants rendered up front to prove the substitution actually reaches
# the component. They must differ; if they do not, plan A is inert.
PROBE_A, PROBE_B = "none", "3"

# Mean per-channel difference below which two renders count as identical. PNG
# encoding is lossless and the page has no animation, so a working substitution
# lands orders of magnitude above this; the tolerance only absorbs a stray
# antialiased pixel.
IDENTICAL_THRESHOLD = 0.01

DIM_OPACITY = 0.28


# --------------------------------------------------------------------------
# Plan A: rewrite the highlight prop's default in the exported HTML.
# --------------------------------------------------------------------------

# The props JSON lives in a data-props attribute, so its quotes are HTML
# escaped -- and the whole template is then embedded as a JSON string inside
# the bundler shell, which leaves the &quot; entities untouched. Match both the
# escaped and the bare form so the script survives a re-export either way.
_QUOTE_FORMS = ("&quot;", '"')


def _highlight_default_pattern(quote: str) -> re.Pattern[str]:
    """Match `"default":"none"` only where it sits inside the highlight block.

    Anchoring on the enum's options list keeps the match off dimOpacity's own
    default and off any other prop a future export might add.
    """
    q = re.escape(quote)
    return re.compile(
        rf"({q}highlight{q}\s*:\s*\{{[^{{}}]*?{q}default{q}\s*:\s*){q}none{q}",
        re.DOTALL,
    )


def substitute_highlight(html: str, value: str) -> str:
    """Return `html` with the highlight prop defaulting to `value`.

    Asserts exactly one match across both quote forms; a zero or multiple match
    means the export's shape changed and the caller must not ship the render.
    """
    matches = [(q, _highlight_default_pattern(q)) for q in _QUOTE_FORMS]
    hits = [(q, pat, m) for q, pat in matches if (m := list(pat.finditer(html)))]
    if not hits:
        raise SystemExit(
            f'FAIL: no `"default":"none"` found inside the highlight prop block of {SOURCE}. '
            "The export's prop declaration changed -- fix the pattern before rendering."
        )
    if len(hits) > 1:
        forms = ", ".join(repr(q) for q, _, _ in hits)
        raise SystemExit(
            f"FAIL: the highlight default matched in multiple quote forms ({forms}) in {SOURCE}. "
            "Ambiguous substitution target -- refusing to guess."
        )
    quote, pattern, found = hits[0]
    if len(found) != 1:
        raise SystemExit(
            f"FAIL: expected exactly 1 highlight default in {SOURCE}, found {len(found)}. "
            "Refusing to substitute."
        )
    return pattern.sub(rf"\g<1>{quote}{value}{quote}", html, count=1)


# --------------------------------------------------------------------------
# Plan B: find the region containers in the rendered DOM, dim by injected CSS.
# --------------------------------------------------------------------------

# The six regions are the top-level absolutely positioned cards of the 1920x1080
# stage: card-sized, chrome-coloured, and laid out in two rows of three. Ordering
# is reading order (row, then column) so region N matches highlight value N.
FIND_REGIONS_JS = """
() => {
  const stage = document.querySelector('x-dc, [data-dc-root]') || document.body;
  const nodes = Array.from(stage.querySelectorAll('div')).filter(el => {
    const cs = getComputedStyle(el);
    if (cs.position !== 'absolute') return false;
    const r = el.getBoundingClientRect();
    return r.width > 400 && r.width < 700 && r.height > 300 && r.height < 500;
  });
  // Drop nested candidates -- keep only the outermost card at each position.
  const tops = nodes.filter(el => !nodes.some(o => o !== el && o.contains(el)));
  tops.sort((a, b) => {
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    return Math.abs(ra.top - rb.top) > 40 ? ra.top - rb.top : ra.left - rb.left;
  });
  return tops.map((el, i) => {
    const mark = 'arch-region-' + (i + 1);
    el.setAttribute('data-arch-region', String(i + 1));
    el.classList.add(mark);
    const r = el.getBoundingClientRect();
    return { index: i + 1, selector: '.' + mark, tag: el.tagName.toLowerCase(),
             left: Math.round(r.left), top: Math.round(r.top),
             width: Math.round(r.width), height: Math.round(r.height) };
  });
}
"""


def plan_b_css(value: str, regions: list[dict[str, object]]) -> str:
    """CSS dimming every region but the target (or nothing, for `none`)."""
    if value == "none":
        return ""
    rules = [
        f"[data-arch-region='{r['index']}'] {{ opacity: {DIM_OPACITY} !important; }}"
        for r in regions
        if str(r["index"]) != value
    ]
    rules.append(
        f"[data-arch-region='{value}'] {{ opacity: 1 !important; "
        "outline: 2px solid #5EEAD4 !important; outline-offset: 10px !important; }}"
    )
    return "\n".join(rules)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _await_ready(page: Page) -> None:
    """Wait for the bundler to finish unpacking, without a fixed sleep.

    The shell shows `#__bundler_loading` ("Unpacking...") and a
    `#__bundler_thumbnail` placeholder, then swaps the whole documentElement for
    the unpacked template. Both markers being gone -- and the component's own
    stage having laid out -- is the real ready signal.
    """
    page.wait_for_load_state("networkidle")
    page.wait_for_function(
        """() => !document.getElementById('__bundler_loading')
                && !document.getElementById('__bundler_thumbnail')""",
        timeout=60_000,
    )
    page.wait_for_function(
        """() => {
             const err = document.getElementById('__bundler_err');
             if (err) throw new Error('bundle error: ' + err.textContent.slice(0, 300));
             return document.querySelectorAll('div').length > 20;
           }""",
        timeout=60_000,
    )
    # Let webfonts settle so glyph metrics are identical across all seven.
    page.evaluate("() => document.fonts && document.fonts.ready")
    page.wait_for_timeout(250)


def render(
    page: Page,
    html: str,
    dest: Path,
    inject_css: str = "",
    mark_regions: bool = False,
) -> list[dict[str, object]]:
    """Load `html` from a temp file next to the source and shoot the viewport.

    The temp file lives in the source directory so the bundler's relative
    resource references resolve exactly as they do for the original export.

    `mark_regions` re-runs the region-marking script after the load. Every load
    is a fresh document, so the `data-arch-region` attributes plan B's CSS keys
    off have to be re-applied here -- marking once and navigating away would
    leave the injected rules matching nothing.
    """
    with tempfile.NamedTemporaryFile(
        "w", suffix=".html", dir=str(SOURCE.parent), delete=False, encoding="utf-8"
    ) as fh:
        tmp = Path(fh.name)
        fh.write(html)
    try:
        page.goto(tmp.as_uri(), wait_until="domcontentloaded")
        _await_ready(page)
        regions: list[dict[str, object]] = page.evaluate(FIND_REGIONS_JS) if mark_regions else []
        if inject_css:
            page.add_style_tag(content=inject_css)
            page.wait_for_timeout(120)
        dest.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(dest), full_page=False)
        return regions
    finally:
        tmp.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Pixel comparison (stdlib only -- no numpy/Pillow dependency)
# --------------------------------------------------------------------------


def _png_rgba_rows(path: Path) -> tuple[int, int, bytes]:
    """Decode a PNG to (width, height, pixel bytes).

    Handles the 8-bit truecolour forms Chromium emits (colour type 2 and 6,
    no interlacing).
    """
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"FAIL: {path} is not a PNG")
    pos, idat, width = 8, bytearray(), 0
    height = bit_depth = colour_type = interlace = 0
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if ctype == b"IHDR":
            width, height, bit_depth, colour_type, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"IEND":
            break
        pos += 12 + length
    if bit_depth != 8 or colour_type not in (2, 6) or interlace:
        raise SystemExit(
            f"FAIL: unsupported PNG form in {path} "
            f"(bit_depth={bit_depth} colour_type={colour_type} interlace={interlace})"
        )
    channels = 3 if colour_type == 2 else 4
    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(height * stride)
    prev = bytearray(stride)
    src = 0
    for y in range(height):
        filt = raw[src]
        src += 1
        line = bytearray(raw[src : src + stride])
        src += stride
        if filt == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filt == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filt == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filt == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif filt != 0:
            raise SystemExit(f"FAIL: unknown PNG filter {filt} in {path}")
        out[y * stride : (y + 1) * stride] = line
        prev = line
    return width, height, bytes(out)


def mean_pixel_difference(a: Path, b: Path) -> float:
    """Mean absolute per-channel difference (0-255) between two same-size PNGs."""
    wa, ha, pa = _png_rgba_rows(a)
    wb, hb, pb = _png_rgba_rows(b)
    if (wa, ha) != (wb, hb):
        raise SystemExit(f"FAIL: size mismatch {a.name} {wa}x{ha} vs {b.name} {wb}x{hb}")
    if len(pa) != len(pb):
        raise SystemExit(f"FAIL: channel-count mismatch between {a.name} and {b.name}")
    total = sum(abs(x - y) for x, y in zip(pa, pb, strict=True))
    return total / len(pa)


def png_size(path: Path) -> tuple[int, int]:
    """Read (width, height) straight out of a PNG's IHDR."""
    data = path.read_bytes()[16:24]
    w, h = struct.unpack(">II", data)
    return w, h


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def main() -> int:
    """Verify the substitution on two probes, then render all seven stills."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe-only", action="store_true", help="render the two probes and stop")
    ap.add_argument("--force-plan-b", action="store_true", help="skip plan A, use CSS injection")
    args = ap.parse_args()

    if not SOURCE.exists():
        raise SystemExit(f"FAIL: {SOURCE} not found")
    source_html = SOURCE.read_text(encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Probes are scratch, not deliverables -- OUT_DIR holds exactly the seven stills.
    probe_ctx = tempfile.TemporaryDirectory(prefix="arch-probe-")
    probe_dir = Path(probe_ctx.name)

    with probe_ctx, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=DEVICE_SCALE_FACTOR)
        page = context.new_page()
        try:
            plan = "B" if args.force_plan_b else "A"
            regions: list[dict[str, object]] = []

            if plan == "A":
                print("Plan A -- rewriting the highlight prop default.")
                pa = probe_dir / f"probe-{PROBE_A}.png"
                pb = probe_dir / f"probe-{PROBE_B}.png"
                render(page, substitute_highlight(source_html, PROBE_A), pa)
                render(page, substitute_highlight(source_html, PROBE_B), pb)
                delta = mean_pixel_difference(pa, pb)
                print(f"  probe '{PROBE_A}' vs '{PROBE_B}': mean pixel difference {delta:.4f}")
                if delta <= IDENTICAL_THRESHOLD:
                    print(
                        "  probes are pixel-identical -- the substitution never reached the "
                        "component. Falling back to plan B rather than shipping seven "
                        "identical images."
                    )
                    plan = "B"
                else:
                    print("  substitution confirmed live.")

            if plan == "B":
                print("Plan B -- injecting per-variant CSS against the rendered regions.")
                regions = render(page, source_html, probe_dir / "probe-dom.png", mark_regions=True)
                if len(regions) != 6:
                    raise SystemExit(
                        f"FAIL: expected 6 region containers in the rendered DOM, found "
                        f"{len(regions)}. Cannot place the highlight."
                    )
                print("  region containers found:")
                for r in regions:
                    print(
                        f"    {r['index']}: {r['selector']} <{r['tag']}> "
                        f"at ({r['left']},{r['top']}) {r['width']}x{r['height']}"
                    )
                pa = probe_dir / f"probe-b-{PROBE_A}.png"
                pb = probe_dir / f"probe-b-{PROBE_B}.png"
                render(page, source_html, pa, plan_b_css(PROBE_A, regions), mark_regions=True)
                render(page, source_html, pb, plan_b_css(PROBE_B, regions), mark_regions=True)
                delta = mean_pixel_difference(pa, pb)
                print(f"  probe '{PROBE_A}' vs '{PROBE_B}': mean pixel difference {delta:.4f}")
                if delta <= IDENTICAL_THRESHOLD:
                    raise SystemExit(
                        "FAIL: plan B probes are pixel-identical too. Neither approach "
                        "changes the render -- refusing to ship seven identical images."
                    )

            if args.probe_only:
                print(f"\n--probe-only: stopping after the probes (plan {plan}).")
                return 0

            print(f"\nRendering seven stills with plan {plan}.")
            written: list[Path] = []
            for value, name in STILLS:
                dest = OUT_DIR / name
                if plan == "A":
                    render(page, substitute_highlight(source_html, value), dest)
                else:
                    render(page, source_html, dest, plan_b_css(value, regions), mark_regions=True)
                written.append(dest)
                w, h = png_size(dest)
                print(f"  highlight={value:>4}  {dest.relative_to(REPO_ROOT)}  {w}x{h}")

            # Every still must differ from the neutral frame (except the neutral
            # frame itself), or a cross-fade would show nothing.
            neutral = written[0]
            print("\nDifference from the neutral frame:")
            for dest in written[1:]:
                d = mean_pixel_difference(neutral, dest)
                status = "ok" if d > IDENTICAL_THRESHOLD else "IDENTICAL"
                print(f"  {dest.name:<24} {d:8.4f}  {status}")
                if d <= IDENTICAL_THRESHOLD:
                    raise SystemExit(f"FAIL: {dest.name} is identical to the neutral frame.")
            print(f"\nDone -- 7 stills in {OUT_DIR.relative_to(REPO_ROOT)} (plan {plan}).")
        finally:
            context.close()
            browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
