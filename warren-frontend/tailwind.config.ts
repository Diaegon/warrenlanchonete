import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        nubank: {
          purple: "#8A05BE",
          dark: "#1a0533",
          card: "#230640",
          border: "#3d1166",
          text: "#e8d5f5",
          muted: "#a78bbf",
        },
        grade: {
          a: "#22c55e",
          b: "#eab308",
          c: "#f97316",
          d: "#ef4444",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
      },
    },
  },
  plugins: [],
};

export default config;
