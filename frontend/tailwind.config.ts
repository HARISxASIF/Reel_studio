import type { Config } from "tailwindcss";

function withOpacity(variableName: string): any {
  return ({ opacityValue }: { opacityValue?: string }) => {
    if (opacityValue !== undefined) {
      return `rgb(var(${variableName}) / ${opacityValue})`;
    }
    return `rgb(var(${variableName}))`;
  };
}

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        heading: ["var(--font-bricolage)", "Bricolage Grotesque", "system-ui", "-apple-system", "sans-serif"],
        sans: ["var(--font-dosis)", "Dosis", "system-ui", "-apple-system", "sans-serif"],
        body: ["var(--font-dosis)", "Dosis", "system-ui", "-apple-system", "sans-serif"],
      },
      colors: {
        // Direct semantic CSS variable mapping
        page: "var(--bg-page)",
        surface: {
          DEFAULT: "var(--bg-surface)",
          raised: "var(--bg-surface-raised)",
        },
        divider: "var(--border-divider)",
        outline: "var(--border-input)",
        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        primary: {
          DEFAULT: "var(--btn-primary)",
          hover: "var(--btn-primary-hover)",
          text: "var(--btn-primary-text)",
        },
        accent: "var(--color-accent)",
        focus: "var(--focus-ring)",
        selected: "var(--bg-selected)",
        "status-success": "var(--color-success)",
        "status-warning": "var(--color-warning)",
        "status-error": "var(--color-error)",
        "video-surround": "var(--bg-video-surround)",

        // Wire existing slate classes to semantic CSS variables with opacity support
        slate: {
          950: withOpacity("--bg-page-rgb"),
          900: withOpacity("--bg-surface-rgb"),
          800: withOpacity("--bg-surface-raised-rgb"),
          700: withOpacity("--border-divider-rgb"),
          600: withOpacity("--border-input-rgb"),
          500: withOpacity("--border-input-rgb"),
          400: withOpacity("--text-secondary-rgb"),
          300: withOpacity("--text-secondary-rgb"),
          200: withOpacity("--text-primary-rgb"),
          100: withOpacity("--text-primary-rgb"),
          50: withOpacity("--text-primary-rgb"),
        },
        // Wire existing indigo classes to primary violet (#7042D2) & accents
        indigo: {
          950: withOpacity("--bg-selected-rgb"),
          900: withOpacity("--bg-selected-rgb"),
          800: withOpacity("--bg-surface-raised-rgb"),
          700: withOpacity("--btn-primary-hover-rgb"),
          600: withOpacity("--btn-primary-rgb"),
          500: withOpacity("--btn-primary-hover-rgb"),
          400: withOpacity("--color-accent-rgb"),
          300: withOpacity("--color-accent-rgb"),
          200: withOpacity("--color-accent-rgb"),
          100: withOpacity("--bg-selected-rgb"),
          50: withOpacity("--bg-selected-rgb"),
        },
      },
    },
  },
  plugins: [],
};
export default config;
