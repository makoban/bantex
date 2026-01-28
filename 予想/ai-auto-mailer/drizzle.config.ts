import { defineConfig } from "drizzle-kit";

const connectionString = process.env.DATABASE_URL;
if (!connectionString) {
  throw new Error("DATABASE_URL is required to run drizzle commands");
}

// URLにSSLパラメータを追加（drizzle-kitのworkaround）
const url = new URL(connectionString);
url.searchParams.set("sslmode", "require");

export default defineConfig({
  schema: "./drizzle/schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  dbCredentials: {
    url: url.toString(),
  },
});
