import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            colors: {
                background: "var(--background)",
                foreground: "var(--foreground)",
                maf: {
                    blue: "#00A6FB",
                    dark: "#0a0c10",
                    card: "#12161b",
                    border: "#1d2127",
                    input: "#080a0d",
                    accent: "#1f6feb",
                    text: {
                        primary: "#ffffff",
                        secondary: "#94a3b8",
                        muted: "#475569",
                    }
                },
                attack: {
                    sqli: "#f87171",
                    xss: "#fbbf24",
                    dos: "#34d399",
                    other: "#a78bfa",
                }
            },
            boxShadow: {
                'glow': '0 0 20px rgba(0, 166, 251, 0.15)',
                'premium': '0 10px 30px -10px rgba(0, 0, 0, 0.5)',
            }
        },
    },
    plugins: [],
};
export default config;
