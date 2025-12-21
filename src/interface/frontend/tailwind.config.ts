import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        "dark-bg": "#15171A",
        "dark-bg-secondary": "#1F2125",
        "dark-text": "#FFFFFF",
        "dark-text-secondary": "#B3B3B3",
        "accent-teal": "#25C5A7",
        "accent-teal-hover": "#1da89c",
      },
      spacing: {
        "container-gap": "clamp(1.5rem, 5vw, 4rem)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
