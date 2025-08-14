import { call, put, takeEvery } from 'redux-saga/effects';
import { getRoutes } from '../../services/feeds/route-service';
import {
  loadingRoutes,
  routesLoaded,
  routesError,
} from '../route-reducer';
import { type Route } from '../../types/Route';

function* fetchRoutesSaga(
  action: ReturnType<typeof loadingRoutes>,
): Generator<any, void, any> {
  try {
    const routes: Route[] = yield call(
      getRoutes,
      action.payload.feedId,
      action.payload.datasetId,
    );
    yield put(routesLoaded(routes));
  } catch (e: any) {
    yield put(routesError(e.message));
  }
}

export function* routeSaga(): Generator<any, void, any> {
  yield takeEvery(loadingRoutes.type, fetchRoutesSaga);
}
