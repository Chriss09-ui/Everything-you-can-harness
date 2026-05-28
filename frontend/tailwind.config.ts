import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

// Design tokens — 来自 marvis-demo.html，所有色值 / 圆角 / 阴影都在这里集中。
// 改 token 必须同步 frontend/STYLE.md。
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f4f3f0",
        sidebar: "#fbfaf8",
        surface: {
          DEFAULT: "#ffffff",
          hover: "#f3f2ef",
        },
        ink: {
          DEFAULT: "#1a1a1a",
          muted: "#8a8a85",
          faint: "#b4b4ae",
        },
        line: {
          DEFAULT: "#eceae6",
          strong: "#e2e0db",
        },
        accent: {
          DEFAULT: "#e5362b",
          soft: "#fdecea",
        },
        ok: {
          DEFAULT: "#1f9d3a",
          soft: "#eaf7ec",
          dot: "#28c840",
        },
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "22px",
        full: "999px",
      },
      boxShadow: {
        "soft-sm": "0 1px 2px rgba(0,0,0,0.04)",
        "soft-md": "0 2px 12px rgba(0,0,0,0.05)",
        "soft-lg": "0 8px 36px rgba(0,0,0,0.07)",
        input: "0 2px 20px rgba(0,0,0,0.05), 0 0 0 1px #eceae6",
        "input-focus": "0 4px 28px rgba(0,0,0,0.07), 0 0 0 1px #e2e0db",
      },
      fontFamily: {
        display: [
          "Bricolage Grotesque",
          "-apple-system",
          "BlinkMacSystemFont",
          "sans-serif",
        ],
        body: [
          "-apple-system",
          "BlinkMacSystemFont",
          "PingFang SC",
          "Helvetica Neue",
          "Segoe UI",
          "sans-serif",
        ],
      },
      width: { sidebar: "264px" },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        blink: {
          "0%, 80%, 100%": { opacity: "0.3", transform: "scale(0.8)" },
          "40%": { opacity: "1", transform: "scale(1)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.5s cubic-bezier(.2,.7,.3,1) both",
        blink: "blink 1.2s infinite both",
      },
    },
  },
  plugins: [animate],
} satisfies Config;
