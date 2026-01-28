import { config } from "@remotion/eslint-config-flat";

export default [
  ...config,
  {
    ignores: [
      "**/予想/**",
      "**/事業構築/**",
      "**/public/**",
      "**/node_modules/**",
      "*.js",
      "*.mjs",
      "*.ts",
      "!src/**"
    ],
  },
];
