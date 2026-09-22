/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts}"],
  theme: {
    extend: {
      colors: {
        panel: "#12151c",
        surface: "#1a1e27",
        accent: "#4caf7d",
      },
    },
  },
  plugins: [],
};
