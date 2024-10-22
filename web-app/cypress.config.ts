import { defineConfig } from 'cypress';
import * as dotenv from 'dotenv';
const localEnv = dotenv.config({ path: './src/.env.dev' }).parsed;
const ciEnv = dotenv.config({ path: './src/.env.test' }).parsed;

const isEnvEmpty = (obj) => {
  return Object.keys(obj).length === 0;
};

const chosenEnv = isEnvEmpty(localEnv) ? ciEnv : localEnv;

export default defineConfig({
  env: chosenEnv,
  e2e: {
    baseUrl: 'http://localhost:3000',
  },
  video: true,
});
