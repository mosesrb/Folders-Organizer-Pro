/** @type {import('tailwindcss').Config} */

// Wraps a CSS variable holding a raw "R G B" triplet so Tailwind can inject
// an alpha channel for opacity-modifier utilities (bg-primary/20, etc.).
// The variable itself must hold "R G B", not a hex string or rgb()/rgba() —
// see the comment at the top of index.css's variable block.
function withOpacity(varName) {
  return `rgb(var(${varName}) / <alpha-value>)`;
}

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        serif: ['"Roboto Slab"', 'Georgia', 'serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        // Every color below points at a CSS custom property defined in
        // index.css ([:root]/[data-theme="light"] vs [data-theme="dark"]).
        // This is deliberate: it means every existing `bg-slate-400`,
        // `text-primary`, `border-primary/20`, etc. utility class across
        // the whole app automatically responds to the theme attribute on
        // <html> with zero changes to any className — only the variable
        // values in index.css differ per theme. Don't replace these with
        // literal hex again; that would silently break dark mode (and
        // every opacity-modifier usage) for whatever token you change.
        background: withOpacity('--color-background'),
        secondary: withOpacity('--color-secondary'),
        card: withOpacity('--color-card'),
        ink: {
          DEFAULT: withOpacity('--color-ink'),
          soft: withOpacity('--color-ink-soft'),
        },
        primary: {
          DEFAULT: withOpacity('--color-primary'),
          dark: withOpacity('--color-primary-dark'),
          light: withOpacity('--color-primary-light'),
        },
        accent: {
          DEFAULT: withOpacity('--color-accent'),
        },
        filed: {
          DEFAULT: withOpacity('--color-filed'),
          light: withOpacity('--color-filed-light'),
          dark: withOpacity('--color-filed-dark'),
        },
        // "on-*" = the text/icon color to use ON TOP of a bg-accent /
        // bg-filed / bg-amber-600 fill. Needed because accent/filed/amber
        // brighten in dark mode (for standalone text contrast) while
        // still needing to pair with readable text when used as a solid
        // button fill — see the 2026-08-19 memories.md entry.
        "on-primary": withOpacity('--on-primary'),
        "on-accent": withOpacity('--on-accent'),
        "on-filed": withOpacity('--on-filed'),
        "on-amber": withOpacity('--on-amber'),
        surface: {
          DEFAULT: "var(--surface-default)",
          hover: "var(--surface-hover)",
          border: "var(--surface-border)",
        },

        // Warm paper-neutral ramp replaces the stock dark "slate" palette
        // used throughout the app's structural chrome (backgrounds, text,
        // borders). Each shade keeps the same *role* across themes (100 =
        // closest to page background, 900 = closest to ink) even though
        // the actual dark-mode values are lightness-inverted.
        slate: {
          50:  withOpacity('--slate-50'),
          100: withOpacity('--slate-100'),
          200: withOpacity('--slate-200'),
          300: withOpacity('--slate-300'),
          400: withOpacity('--slate-400'),
          500: withOpacity('--slate-500'),
          600: withOpacity('--slate-600'),
          700: withOpacity('--slate-700'),
          800: withOpacity('--slate-800'),
          900: withOpacity('--slate-900'),
          950: withOpacity('--slate-950'),
        },

        // Destructive / stamp-red family (was the stock "red")
        red: {
          300: withOpacity('--red-300'), 400: withOpacity('--red-400'), 500: withOpacity('--red-500'),
          600: withOpacity('--red-600'), 700: withOpacity('--red-700'), 800: withOpacity('--red-800'), 900: withOpacity('--red-900'),
        },

        // The app previously used a different neon hue per feature card
        // (pink, indigo, violet, cyan, sky, teal, emerald, amber, orange).
        // Filing Cabinet intentionally restrains this to three families:
        // manila (primary/neutral), filed-green (positive), rust (caution)
        // — so every card reads as "the same filing system", not a rainbow
        // of unrelated brand colors.
        pink:    { 300: withOpacity('--pink-300'), 400: withOpacity('--pink-400'), 500: withOpacity('--pink-500'), 600: withOpacity('--pink-600'), 700: withOpacity('--pink-700') },
        indigo:  { 300: withOpacity('--indigo-300'), 400: withOpacity('--indigo-400'), 500: withOpacity('--indigo-500'), 600: withOpacity('--indigo-600'), 700: withOpacity('--indigo-700') },
        violet:  { 300: withOpacity('--violet-300'), 400: withOpacity('--violet-400'), 500: withOpacity('--violet-500'), 600: withOpacity('--violet-600') },
        cyan:    { 300: withOpacity('--cyan-300'), 400: withOpacity('--cyan-400'), 500: withOpacity('--cyan-500'), 600: withOpacity('--cyan-600'), 700: withOpacity('--cyan-700') },
        sky:     { 400: withOpacity('--sky-400'), 500: withOpacity('--sky-500'), 600: withOpacity('--sky-600') },
        teal:    { 400: withOpacity('--teal-400'), 500: withOpacity('--teal-500'), 600: withOpacity('--teal-600') },
        emerald: { 300: withOpacity('--emerald-300'), 400: withOpacity('--emerald-400'), 500: withOpacity('--emerald-500'), 600: withOpacity('--emerald-600'), 700: withOpacity('--emerald-700') },
        orange:  { 400: withOpacity('--orange-400'), 500: withOpacity('--orange-500'), 600: withOpacity('--orange-600') },
        amber:   { 400: withOpacity('--amber-400'), 500: withOpacity('--amber-500'), 600: withOpacity('--amber-600') },
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
