import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "#d9e2ec",
        background: "#f8fafc",
        foreground: "#0f172a",
        primary: "#047857",
        muted: "#64748b",
      },
    },
  },
  plugins: [],
};

export default config;
