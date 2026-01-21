import createWebStorage from 'redux-persist/lib/storage/createWebStorage';

const createNoopStorage = (): {
  getItem: (key: string) => Promise<string | null>;
  setItem: (key: string, value: string) => Promise<string>;
  removeItem: (key: string) => Promise<void>;
} => {
  return {
    async getItem(_key: string) {
      return await Promise.resolve(null);
    },
    async setItem(_key: string, value: string) {
      return await Promise.resolve(value);
    },
    async removeItem(_key: string) {
      await Promise.resolve();
    },
  };
};

const storage =
  typeof window !== 'undefined'
    ? createWebStorage('local')
    : createNoopStorage();

export default storage;
