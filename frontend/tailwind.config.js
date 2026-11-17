/** @type {import('tailwindcss').Config} */
// Hệ màu "phòng điều khiển chuỗi lạnh":
//   ink   — nền sidebar / chữ đậm      cold  — màu chủ đạo (chuỗi lạnh)
//   leaf  — tươi / đạt                 proof — bằng chứng trên sổ cái (blockchain)
//   warn  — cần chú ý                  danger — vi phạm / sai lệch
const cold = { 50: "#e8f4f6", 100: "#cfe8ec", 200: "#a3d3dc", 300: "#6db7c5", 400: "#3b98aa", 500: "#1a7f93", 600: "#0f6a7c", 700: "#0d5664", 800: "#0d4651", 900: "#0c3a43" };

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: "#08130f", 900: "#0d1c17", 800: "#142a23", 700: "#1d3a31", 600: "#2b4d42", 500: "#547366", 400: "#7f988f", 300: "#a9bcb5" },
        paper: "#f2f5f3",
        line: "#dfe6e2",
        cold,
        brand: cold,
        leaf: { 50: "#ebf6ee", 100: "#d3ecd9", 500: "#2f9a52", 600: "#257d42", 700: "#1d6334" },
        proof: { 50: "#eef0fd", 100: "#dde0fb", 500: "#5057d8", 600: "#3f45c0", 700: "#3237a0" },
        warn: { 50: "#fdf4e3", 100: "#fbe6bf", 500: "#d48a0c", 600: "#b07106", 700: "#8a5806" },
        danger: { 50: "#fdecea", 100: "#f9d3cf", 500: "#d6453b", 600: "#b9342b", 700: "#962920" },
      },
      fontFamily: {
        sans: ['"Be Vietnam Pro"', "Segoe UI", "system-ui", "sans-serif"],
        display: ["Lexend", '"Be Vietnam Pro"', "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(13, 28, 23, 0.05), 0 1px 1px rgba(13, 28, 23, 0.03)",
        lift: "0 10px 30px -12px rgba(13, 28, 23, 0.25)",
      },
    },
  },
  plugins: [],
};
