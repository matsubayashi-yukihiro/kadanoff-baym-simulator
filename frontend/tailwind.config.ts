import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#14202b",
          subtle: "#455468",
          muted: "#6c7a8e",
        },
        accent: {
          DEFAULT: "#166570",
          strong: "#0f4850",
          soft: "#b8e2dd",
          secondary: "#344767",
        },
        panel: {
          DEFAULT: "rgba(248, 251, 253, 0.92)",
          strong: "rgba(252, 253, 255, 0.98)",
          border: "rgba(32, 52, 79, 0.12)",
        },
        success: "#1f7a5c",
        danger: "#a12b2b",
        queued: "#8a6117",
        border: {
          DEFAULT: "rgba(32, 52, 79, 0.12)",
          soft: "rgba(32, 52, 79, 0.08)",
        },
        card: {
          DEFAULT: "rgba(255, 255, 255, 0.74)",
          border: "rgba(32, 52, 79, 0.08)",
        },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', '"Avenir Next"', '"Segoe UI"', "sans-serif"],
        mono: ['"IBM Plex Mono"', '"SFMono-Regular"', "monospace"],
        heading: ['"IBM Plex Sans"', '"Avenir Next"', '"Segoe UI"', "sans-serif"],
      },
      boxShadow: {
        panel: "0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06)",
        card: "0 1px 2px rgba(0, 0, 0, 0.05)",
        "card-active":
          "inset 0 0 0 1px rgba(22, 101, 112, 0.12), 0 1px 3px rgba(0, 0, 0, 0.08)",
        "btn-primary": "0 1px 3px rgba(0, 0, 0, 0.1)",
        "btn-danger": "0 1px 3px rgba(161, 43, 43, 0.12)",
        topbar: "0 1px 3px rgba(0, 0, 0, 0.06)",
      },
      maxWidth: {
        page: "1780px",
      },
      borderRadius: {
        panel: "8px",
        card: "6px",
        btn: "6px",
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
