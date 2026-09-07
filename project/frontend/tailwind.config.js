/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#16212E",
        paper: "#EEF0EE",
        surface: "#FFFFFF",
        line: "#D7DBD6",
        accent: {
          DEFAULT: "#2B6777",
          dark: "#1E4B57",
          light: "#DCE9EB",
        },
        risk: {
          high: "#A8342A",
          highBg: "#F6E4E1",
          medium: "#B8842A",
          mediumBg: "#F5EBDA",
          low: "#3F7A52",
          lowBg: "#E2EEE4",
        },
        muted: "#5B6660",
      },
      fontFamily: {
        display: ["Newsreader", "serif"],
        sans: ["IBM Plex Sans", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
