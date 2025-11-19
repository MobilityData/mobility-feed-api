import {
  persistReducer,
  FLUSH,
  REHYDRATE,
  PAUSE,
  PERSIST,
  PURGE,
  REGISTER,
} from 'redux-persist';
import storage from 'redux-persist/lib/storage';
import {
  configureStore,
  type ThunkAction,
  type Action,
} from '@reduxjs/toolkit';
import createSagaMiddleware from '@redux-saga/core';
import rootSaga from './saga/root-saga';

import rootReducer from './reducers';
import { createReduxEnhancer } from '@sentry/react';

const persistConfig = {
  key: 'root',
  version: 1,
  storage,
  blacklist: ['userProfile.errors', 'userProfile.isRefreshingAccessToken'],
};

const persistedReducer = persistReducer(persistConfig, rootReducer);

const sagaMiddleware = createSagaMiddleware();

// Light-weight state sanitizer used by Sentry redux enhancer
const sanitizeState = (state: unknown): unknown => {
  if (state == null || typeof state !== 'object') {
    return state;
  }
  const copy: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(state)) {
    if (v == null) {
      copy[k] = v;
    } else if (Array.isArray(v)) {
      copy[k] = { __type: 'array', length: v.length };
    } else if (typeof v === 'object') {
      copy[k] = { __type: 'object', keys: Object.keys(v).length };
    } else {
      copy[k] = v;
    }
  }
  return copy;
};

const sentryReduxEnhancer = createReduxEnhancer({
  attachReduxState: true,
  stateTransformer: sanitizeState,
});

/* eslint-disable */
const makeStore = () =>
  configureStore({
    reducer: persistedReducer,
    devTools: process.env.NODE_ENV !== 'production',
    middleware: (getDefaultMiddleware) => [
      ...getDefaultMiddleware({
        serializableCheck: {
          ignoredActions: [FLUSH, REHYDRATE, PAUSE, PERSIST, PURGE, REGISTER],
        },
      }),
      sagaMiddleware,
    ],
    enhancers: (existing) =>
      sentryReduxEnhancer ? [...existing, sentryReduxEnhancer] : existing,
  });
/* eslint-enable */

export const store = makeStore();

// Expose store to Cypress e2e tests
/* eslint-disable */
if (window.Cypress) {
  (window as any).store = store;
}
/* eslint-enable */

sagaMiddleware.run(rootSaga);

export type RootState = ReturnType<typeof persistedReducer>;
export type AppDispatch = typeof store.dispatch;
export type AppThunk<ReturnType = void> = ThunkAction<
  ReturnType,
  RootState,
  unknown,
  Action<string>
>;
