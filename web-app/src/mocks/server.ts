import { setupServer } from 'msw/node';
import { handlers } from './handlers';

// Create the MSW server for Node.js (server-side) for e2e tests and SSR mocking
export const server = setupServer(...handlers);
