/**
 * This file is loaded before all tests.
 */
const setup = async (): Promise<void> => {
  process.env.TZ = 'UTC';
};

export default setup;
