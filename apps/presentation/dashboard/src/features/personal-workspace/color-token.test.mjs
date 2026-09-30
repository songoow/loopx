import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

/**
 * Contract for the base colour tokens in `styles.css`.
 *
 * `docs/development/design.md` names these eleven values as the canonical
 * palette, and stylesheets used to reference them through
 * `var(--color-x, #fallback)` while nothing defined them — so every reference
 * silently took its fallback, and the documented token names existed only as
 * repeated literals. Defining the tokens and dropping the fallbacks is what
 * makes the palette a single source of truth instead of eleven coincidences.
 *
 * Two things are easy to undo by accident and invisible when undone:
 *
 *   1. Deleting a token definition. The reference then resolves to nothing and
 *      the browser drops that declaration — the same silent failure the font
 *      tokens had. `scripts/check-css-custom-properties.mjs` catches the bare
 *      reference, but only this test pins *what* the tokens are.
 *   2. Re-introducing a fallback. `var(--color-muted, #8f8f8f)` looks harmless
 *      and hides a missing definition behind a literal, which is how the
 *      original drift survived review.
 *
 * The tokens deliberately live in a plain `:root` block, not a Tailwind
 * `@theme` block: Tailwind v4 emits only the theme variables that some `var()`
 * references, so an unreferenced token is dropped from the build output.
 */

const dashboardStyles = readFileSync(new URL("../../styles.css", import.meta.url), "utf8");

// Every canonical token is defined with the documented value.
const EXPECTED = {
  "--color-ink": "#171717",
  "--color-body": "#4d4d4d",
  "--color-muted": "#8f8f8f",
  "--color-faint": "#a1a1a1",
  "--color-canvas": "#fafafa",
  "--color-surface": "#ffffff",
  "--color-surface-soft": "#f2f2f2",
  "--color-border": "#ebebeb",
  "--color-link": "#0070f3",
  "--color-danger": "#ee0000",
  "--color-warning": "#f5a623",
};

for (const [token, value] of Object.entries(EXPECTED)) {
  const pattern = new RegExp(`\\n\\s*${token}:\\s*${value};`, "i");
  assert.match(dashboardStyles, pattern, `${token} is defined as ${value}`);
}

// The palette is declared in `:root`, where the references resolve.
assert.match(
  dashboardStyles,
  /:root\s*\{[\s\S]*--color-ink: #171717;[\s\S]*\}/,
  "the colour tokens are declared in :root",
);

// It is NOT a Tailwind @theme block: v4 prunes unreferenced theme variables, so
// a token nothing reads yet would vanish from the output.
const themeBlock = /@theme\s*\{([\s\S]*?)\}/.exec(dashboardStyles);
assert.ok(
  !themeBlock || !themeBlock[1].includes("--color-ink"),
  "the colour tokens are not declared inside @theme, which prunes unreferenced variables",
);

// No stylesheet re-introduces a fallback for a token that is now defined.
// A fallback is only appropriate for a genuinely optional token, and none of
// these eleven are optional.
const stylesheets = [
  dashboardStyles,
  readFileSync(new URL("./personal-workspace.css", import.meta.url), "utf8"),
  readFileSync(new URL("./collaboration-card.css", import.meta.url), "utf8"),
  readFileSync(new URL("./delivery-review.css", import.meta.url), "utf8"),
];

for (const [index, source] of stylesheets.entries()) {
  const withoutComments = source.replace(/\/\*[\s\S]*?\*\//g, "");
  const fallbackSignatures = [
    ...withoutComments.matchAll(/var\(\s*(--color-[a-z-]+)\s*,\s*[^)]+\)/g),
  ].map((match) => match[1]);
  assert.deepEqual(
    [...new Set(fallbackSignatures)],
    [],
    `stylesheet #${index} re-introduces a fallback for a defined token, which hides a missing definition`,
  );
}

console.log("color-token contract: ok");
