import { defineConfig } from "vite";

const replitHost =
  "07298b47-3865-4d35-8cbc-54def4c93177-00-37m7deo0itehq-cwoemdur.kirk.replit.dev";

export default defineConfig({
  server: {
    host: "0.0.0.0",
    allowedHosts: [replitHost, ".replit.dev", ".kirk.replit.dev"],
  },
  preview: {
    host: "0.0.0.0",
    allowedHosts: [replitHost, ".replit.dev", ".kirk.replit.dev"],
  },
});
