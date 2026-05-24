import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        pitch: {
          900: "#0a1628",
          800: "#0f2137",
          700: "#163352",
          500: "#1e6b4a",
          400: "#2d9f6f",
        },
        gold: { 400: "#f5c542", 500: "#e6a817" },
      },
    },
  },
  plugins: [],
};
export default config;
