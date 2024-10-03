import { defineConfig } from 'cypress';
import * as dotenv from 'dotenv';
const localEnv = dotenv.config({ path: './src/.env.dev' }).parsed;
const ciEnv = dotenv.config({ path: './src/.env.test' }).parsed;

export default defineConfig({
  env: localEnv ?? ciEnv,
  e2e: {
    baseUrl: 'http://localhost:3000'
  },
  video: true,
});
