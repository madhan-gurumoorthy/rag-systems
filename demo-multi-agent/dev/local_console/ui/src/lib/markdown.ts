import DOMPurify from "dompurify";
import { marked } from "marked";

/**
 * Render trusted-but-LLM-authored markdown to sanitized HTML.
 *
 * `marked` handles the parse → HTML step (GFM tables, fenced code,
 * task lists). `DOMPurify` strips anything that could escape the
 * bubble (script tags, on* attrs, javascript: URLs). The console is
 * local-only, but LLM output is the equivalent of untrusted input as
 * far as the renderer is concerned, so we never `dangerouslySetInner-
 * HTML` raw marked output.
 *
 * Before handing to `marked`, the input is run through
 * `normalizeTables()` so ASCII grid tables (`+---+---+` borders),
 * box-drawing tables (`┌─┬─┐`, `│`, `├─┼─┤`, `└─┴─┘`), and pipe-row
 * blocks missing the GFM `|---|---|` separator are rewritten into
 * canonical GFM pipe tables. Without this step LLM-emitted tables
 * frequently come through as a wall of monospaced text.
 *
 * Synchronous flavour because we render inside React's render pass.
 * `marked.parse` can return a Promise when async extensions are
 * registered; we register none, so the sync `parse` overload is safe.
 */
marked.setOptions({
  gfm: true,
  breaks: false,
});

export function renderMarkdown(input: string): string {
  if (!input) return "";
  const normalized = normalizeTables(input);
  const html = marked.parse(normalized, { async: false }) as string;
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
  });
}

// ─────────────────────────────────────────────────────────────────
// Table normalization
// ─────────────────────────────────────────────────────────────────

/** ASCII grid border row: `+---+===+---+`. */
const ASCII_BORDER_RE = /^\s*\+[-=+\s]*\+\s*$/;
/** Box-drawing border row: corners + horizontals. */
const BOX_BORDER_RE = /^\s*[┌┬┐├┼┤└┴┘╔╦╗╠╬╣╚╩╝╭┯╮╰┷╯][─━═╌╍┄┅┬┴┼┤├╦╩╬╣╠╤╧╪┯┷+]+[┐┤┘╗╣╝╮╯+]?\s*$/;
/** GFM separator row already present: `| --- | :--: |`. */
const GFM_SEP_RE = /^\s*\|?\s*:?-{3,}:?(\s*\|\s*:?-{3,}:?)*\s*\|?\s*$/;

/** A line that looks like a pipe data row: `| a | b | c |` or `a | b | c`. */
function looksLikeDataRow(line: string): boolean {
  // Replace box-drawing verticals with `|` so we can count cells uniformly.
  const t = line.replace(/[│║]/g, "|").trim();
  if (!t) return false;
  // Must contain at least one pipe and not be a pure border row.
  if (!t.includes("|")) return false;
  if (ASCII_BORDER_RE.test(line) || BOX_BORDER_RE.test(line)) return false;
  // Must have at least 2 cells worth of content.
  const cells = t.replace(/^\||\|$/g, "").split("|");
  return cells.length >= 2 && cells.some((c) => c.trim().length > 0);
}

/** Count the cells in a (possibly box-drawing) data row. */
function countCells(line: string): number {
  const t = line.replace(/[│║]/g, "|").trim().replace(/^\||\|$/g, "");
  return t.split("|").length;
}

/** Normalize one data row into a GFM pipe row: `| a | b | c |`. */
function toPipeRow(line: string): string {
  const t = line.replace(/[│║]/g, "|").trim();
  // Strip leading/trailing pipes, split, trim cells, re-emit.
  const cells = t.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
  return "| " + cells.join(" | ") + " |";
}

/** Build a GFM separator row matching the given cell count. */
function makeSeparator(cells: number): string {
  return "|" + Array(cells).fill(" --- ").join("|") + "|";
}

/**
 * Walk the input line-by-line. When a contiguous run of rows looks
 * like a table (ASCII grid, box-drawing, or unseparated pipe rows),
 * rewrite it into a canonical GFM pipe table. Skips content inside
 * fenced code blocks so LLM-emitted ``` blocks stay verbatim.
 */
export function normalizeTables(input: string): string {
  const lines = input.split(/\r?\n/);
  const out: string[] = [];
  let inFence = false;
  let fenceMarker = "";

  let i = 0;
  while (i < lines.length) {
    const line = lines[i] ?? "";
    const trimmed = line.trim();

    // Track fenced code blocks — never rewrite inside them.
    if (!inFence) {
      const fenceMatch = /^(\s*)(```+|~~~+)(.*)$/.exec(line);
      if (fenceMatch) {
        inFence = true;
        fenceMarker = fenceMatch[2] ?? "```";
        out.push(line);
        i++;
        continue;
      }
    } else {
      out.push(line);
      if (trimmed.startsWith(fenceMarker)) inFence = false;
      i++;
      continue;
    }

    // Try to consume a table block starting at i.
    const consumed = tryConsumeTable(lines, i, out);
    if (consumed > 0) {
      i += consumed;
      continue;
    }

    out.push(line);
    i++;
  }

  return out.join("\n");
}

/**
 * If lines starting at `start` form a table, append the rewritten GFM
 * pipe table to `out` and return how many input lines were consumed.
 * Otherwise return 0 and leave `out` untouched.
 */
function tryConsumeTable(
  lines: string[],
  start: number,
  out: string[],
): number {
  // Scan forward gathering candidate rows. A table block runs until we
  // hit a blank line or something that's neither a border nor a data row.
  let end = start;
  let dataRows = 0;
  let borderRows = 0;
  let hasGfmSep = false;
  let hasAsciiBorder = false;
  let hasBoxBorder = false;

  while (end < lines.length) {
    const ln = lines[end] ?? "";
    const t = ln.trim();
    if (!t) break;
    if (ASCII_BORDER_RE.test(ln)) {
      hasAsciiBorder = true;
      borderRows++;
      end++;
      continue;
    }
    if (BOX_BORDER_RE.test(ln)) {
      hasBoxBorder = true;
      borderRows++;
      end++;
      continue;
    }
    if (GFM_SEP_RE.test(ln)) {
      hasGfmSep = true;
      end++;
      continue;
    }
    if (looksLikeDataRow(ln)) {
      dataRows++;
      end++;
      continue;
    }
    break;
  }

  // No table here.
  if (dataRows < 1) return 0;

  // Decide whether this block is actually a table.
  // - ASCII grid: ≥1 border row + ≥1 data row
  // - Box-drawing: ≥1 box border + ≥1 data row
  // - Bare pipe rows without GFM sep: need ≥2 data rows
  // - If GFM sep is already present, leave the block alone (marked
  //   handles it natively).
  if (hasGfmSep && !hasAsciiBorder && !hasBoxBorder) return 0;
  const isTable =
    (hasAsciiBorder && dataRows >= 1) ||
    (hasBoxBorder && dataRows >= 1) ||
    (!hasAsciiBorder && !hasBoxBorder && !hasGfmSep && dataRows >= 2);
  if (!isTable) return 0;

  // Collect just the data rows (drop borders + any stray GFM sep —
  // we'll emit a fresh one).
  const rows: string[] = [];
  for (let k = start; k < end; k++) {
    const ln = lines[k] ?? "";
    if (ASCII_BORDER_RE.test(ln)) continue;
    if (BOX_BORDER_RE.test(ln)) continue;
    if (GFM_SEP_RE.test(ln)) continue;
    if (looksLikeDataRow(ln)) rows.push(toPipeRow(ln));
  }
  if (rows.length < 1) return 0;

  // Cell count = max across rows (LLMs occasionally drop a trailing
  // empty cell; padding short rows keeps the table well-formed).
  const cellCount = rows.reduce(
    (m, r) => Math.max(m, countCells(r)),
    0,
  );
  if (cellCount < 2) return 0;

  const padded = rows.map((r) => padCells(r, cellCount));

  // Pipe-only blocks with exactly one row aren't a table — leave them.
  if (!hasAsciiBorder && !hasBoxBorder && padded.length < 2) return 0;

  // Emit: header row, separator, body rows. A leading blank line
  // ensures marked treats the table as a fresh block.
  const lastOut = out[out.length - 1];
  if (out.length > 0 && lastOut !== undefined && lastOut.trim() !== "") {
    out.push("");
  }
  out.push(padded[0] ?? "");
  out.push(makeSeparator(cellCount));
  for (let k = 1; k < padded.length; k++) out.push(padded[k] ?? "");
  out.push(""); // trailing blank so the next block re-starts cleanly

  return end - start;
}

/** Pad a pipe row out to `n` cells by appending empty cells. */
function padCells(row: string, n: number): string {
  const cells = row
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((c) => c.trim());
  while (cells.length < n) cells.push("");
  return "| " + cells.join(" | ") + " |";
}
