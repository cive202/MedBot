/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--bg) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        text: "rgb(var(--text) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        primary: "rgb(var(--primary) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      backdropBlur: { xs: "2px" },
      keyframes: {
        breathe: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-2px)" },
        },
        wave: {
          "0%, 100%": { transform: "rotate(-15deg)" },
          "50%": { transform: "rotate(25deg)" },
        },
        nod: {
          "0%, 100%": { transform: "rotate(0deg)" },
          "50%": { transform: "rotate(-6deg)" },
        },
        blink: {
          "0%, 92%, 100%": { transform: "scaleY(1)" },
          "95%": { transform: "scaleY(0.1)" },
        },
        speak: {
          "0%, 100%": { transform: "scaleY(1)" },
          "50%": { transform: "scaleY(0.5)" },
        },
        pop: {
          "0%": { transform: "scale(0)", opacity: "0" },
          "60%": { transform: "scale(1.2)", opacity: "1" },
          "100%": { transform: "scale(1)", opacity: "1" },
        },
        bobble: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-4px)" },
        },
        thinkDot: {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.4" },
          "40%": { transform: "scale(1)", opacity: "1" },
        },
        bubbleIn: {
          "0%": { transform: "translateY(6px) scale(0.92)", opacity: "0" },
          "100%": { transform: "translateY(0) scale(1)", opacity: "1" },
        },
        sparkle: {
          "0%, 100%": { opacity: "0", transform: "scale(0.6) rotate(0deg)" },
          "50%": { opacity: "1", transform: "scale(1) rotate(20deg)" },
        },
      },
      animation: {
        breathe: "breathe 3s ease-in-out infinite",
        wave: "wave 0.9s ease-in-out infinite",
        nod: "nod 1.6s ease-in-out infinite",
        blink: "blink 4.5s ease-in-out infinite",
        speak: "speak 0.45s ease-in-out infinite",
        pop: "pop 0.35s ease-out forwards",
        bobble: "bobble 1.2s ease-in-out infinite",
        "think-dot-1": "thinkDot 1.2s ease-in-out 0s infinite",
        "think-dot-2": "thinkDot 1.2s ease-in-out 0.2s infinite",
        "think-dot-3": "thinkDot 1.2s ease-in-out 0.4s infinite",
        "bubble-in": "bubbleIn 0.25s ease-out forwards",
        sparkle: "sparkle 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
