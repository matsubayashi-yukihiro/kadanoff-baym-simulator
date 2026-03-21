import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0c1229",
          subtle: "#374165",
          muted: "#6571a3",
        },
        accent: {
          DEFAULT: "#4c42e8",
          strong: "#3a30d0",
          soft: "#e8e6fb",
          secondary: "#5c51f0",
        },
        panel: {
          DEFAULT: "rgba(247, 248, 252, 0.92)",
          strong: "rgba(252, 252, 255, 0.98)",
          border: "rgba(12, 18, 41, 0.11)",
        },
        success: "#1a7a4a",
        danger: "#c0334a",
        queued: "#9b6d14",
        border: {
          DEFAULT: "rgba(12, 18, 41, 0.11)",
          soft: "rgba(12, 18, 41, 0.07)",
        },
        card: {
          DEFAULT: "rgba(255, 255, 255, 0.74)",
          border: "rgba(12, 18, 41, 0.08)",
        },
      },
      fontFamily: {
        sans: ['"Manrope"', '"Avenir Next"', '"Segoe UI"', "sans-serif"],
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', '"SFMono-Regular"', "monospace"],
        heading: ['"Manrope"', '"Avenir Next"', '"Segoe UI"', "sans-serif"],
      },
      boxShadow: {
        panel: "0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06)",
        card: "0 1px 2px rgba(0, 0, 0, 0.05)",
        "card-active":
          "inset 0 0 0 1px rgba(76, 66, 232, 0.14), 0 1px 3px rgba(0, 0, 0, 0.08)",
        "btn-primary": "0 1px 3px rgba(76, 66, 232, 0.18)",
        "btn-danger": "0 1px 3px rgba(192, 51, 74, 0.12)",
        topbar: "0 1px 3px rgba(0, 0, 0, 0.06)",
      },
      maxWidth: {
        page: "1780px",
      },
      borderRadius: {
        panel: "8px",
        card: "6px",
        btn: "5px",
      },
      keyframes: {
        "rise-in": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "rise-in": "rise-in 460ms ease both",
        "fade-in": "fade-in 0.2s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
