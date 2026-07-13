/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        serif: ['"Roboto Slab"', 'Georgia', 'serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        background: "#F3EEE4",   // paper cream — page bg
        secondary: "#EAE1CD",    // card stock — recessed panel bg
        ink: {
          DEFAULT: "#1F1B16",    // primary text
          soft: "#4A4238",       // secondary text
        },
        primary: {
          DEFAULT: "#8B6A3F",    // manila brown — primary actions/links
          dark: "#6B4F2C",
          light: "#B08356",
        },
        accent: {
          DEFAULT: "#8A2E2E",    // stamp red — destructive/alert
        },
        filed: {
          DEFAULT: "#3D5A45",    // filed-away green — success/positive
          light: "#5C7A62",
          dark: "#2A4030",
        },
        surface: {
          DEFAULT: "rgba(31, 27, 22, 0.03)",
          hover: "rgba(31, 27, 22, 0.06)",
          border: "rgba(31, 27, 22, 0.14)",
        },

        // Warm paper-neutral ramp replaces the stock dark "slate" palette
        // used throughout the app's structural chrome (backgrounds, text,
        // borders) — this single remap converts most of the app from a
        // near-black dashboard to a cream paper surface with no per-line edits.
        slate: {
          50:  "#FBF8F1",
          100: "#F3EEE4",
          200: "#EAE1CD",
          300: "#D8CDB8",
          400: "#B7A98C",
          500: "#8C7F68",
          600: "#6B5F4D",
          700: "#4A4238",
          800: "#33291E",
          900: "#241D15",
          950: "#1F1B16",
        },

        // Destructive / stamp-red family (was the stock "red")
        red: {
          300: "#D9A3A3", 400: "#C46E6E", 500: "#A83D3D",
          600: "#8A2E2E", 700: "#6E2323", 800: "#521A1A", 900: "#3A1212",
        },

        // The app previously used a different neon hue per feature card
        // (pink, indigo, violet, cyan, sky, teal, emerald, amber, orange).
        // Filing Cabinet intentionally restrains this to three families:
        // manila (primary/neutral), filed-green (positive), rust (caution)
        // — so every card reads as "the same filing system", not a rainbow
        // of unrelated brand colors.
        pink:    { 300: "#D9BFA3", 400: "#C49A6E", 500: "#B08356", 600: "#8B6A3F", 700: "#6B4F2C" },
        indigo:  { 300: "#C9BBA3", 400: "#A68C63", 500: "#8B6A3F", 600: "#6B4F2C", 700: "#523D22" },
        violet:  { 300: "#C4B29A", 400: "#9C7E52", 500: "#7D6136", 600: "#6B4F2C" },
        cyan:    { 300: "#B7A98C", 400: "#8C7F68", 500: "#8B6A3F", 600: "#6B4F2C", 700: "#523D22" },
        sky:     { 400: "#8C7F68", 500: "#8B6A3F", 600: "#6B4F2C" },
        teal:    { 400: "#7A9683", 500: "#5C7A62", 600: "#3D5A45" },
        emerald: { 300: "#A9C2AE", 400: "#7A9683", 500: "#5C7A62", 600: "#3D5A45", 700: "#2A4030" },
        orange:  { 400: "#C08247", 500: "#A0632F", 600: "#824E24" },
        amber:   { 400: "#C79A56", 500: "#A87A34", 600: "#8B6226" },
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
