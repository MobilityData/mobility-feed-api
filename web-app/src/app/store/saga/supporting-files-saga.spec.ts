import { runSaga } from 'redux-saga';
import * as http from '../../services/http';
import {
  loadingSupportingFile,
  loadingSupportingFileSuccess,
  loadingSupportingFileFail,
} from '../supporting-files-reducer';
import {
  loadSupportingFileSaga,
  buildRoutesUrl,
} from './supporting-files-saga';

// Mock the entire http module
jest.mock('../../services/http', () => ({
  getJson: jest.fn(),
}));

const mockedHttp = http as jest.Mocked<typeof http>;

describe('supporting-files-saga', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('worker saga dispatches success when getJson resolves', async () => {
    const fakeData = {
      type: 'FeatureCollection',
      features: [],
      extracted_at: '2025-01-01T00:00:00Z',
      extraction_url: 'http://example.com/source',
    };
    mockedHttp.getJson.mockResolvedValue(fakeData);

    const dispatched: unknown[] = [];

    await runSaga(
      {
        dispatch: (action) => dispatched.push(action),
        getState: () => ({}),
      },
      loadSupportingFileSaga,
      loadingSupportingFile({
        key: 'gtfsGeolocationGeojson',
        url: 'http://example.com',
      }),
    ).toPromise();

    expect(mockedHttp.getJson).toHaveBeenCalledWith('http://example.com');
    expect(dispatched).toContainEqual(
      loadingSupportingFileSuccess({
        key: 'gtfsGeolocationGeojson',
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-expect-error
        data: fakeData,
      }),
    );
  });

  it('worker saga dispatches fail when getJson throws', async () => {
    mockedHttp.getJson.mockRejectedValue(new Error('Network error'));

    const dispatched: unknown[] = [];

    await runSaga(
      {
        dispatch: (action) => dispatched.push(action),
        getState: () => ({}),
      },
      loadSupportingFileSaga,
      loadingSupportingFile({
        key: 'gtfsGeolocationGeojson',
        url: 'http://example.com',
      }),
    ).toPromise();

    expect(mockedHttp.getJson).toHaveBeenCalledWith('http://example.com');
    expect(
      dispatched.some(
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-expect-error
        (action) => action.type === loadingSupportingFileFail.type,
      ),
    ).toBe(true);
  });

  it('buildRoutesUrl creates correct URL', () => {
    const url = buildRoutesUrl('mdb-1', 'mdb-1-20250101');
    expect(url).toContain(
      'files.mobilitydatabase.org/mdb-1/mdb-1-20250101/pmtiles/routes.json',
    );
  });
});
