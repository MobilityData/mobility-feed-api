import {
  getLocationName,
  isValidFeedLink,
  type EntityLocations,
} from './utils';

const mockLocationMultiple: EntityLocations = [
  {
    country_code: 'US',
    country: 'United States',
    subdivision_name: 'California',
    municipality: 'Los Angeles',
  },
  {
    country_code: 'CA',
    country: 'Canada',
    subdivision_name: 'Ontario',
    municipality: 'Toronto',
  },
];

const mockLocationSingle: EntityLocations = [
  {
    country_code: 'US',
    country: 'United States',
    subdivision_name: 'California',
    municipality: 'Los Angeles',
  },
];

const mockLocationMultipleMinimal: EntityLocations = [
  {
    country_code: 'ES',
    country: 'Spain',
  },
  {
    country_code: 'CA',
    country: 'Canada',
    subdivision_name: 'Ontario',
    municipality: 'Toronto',
  },
];

describe('Feeds Utils', () => {
  it('should format location names correctly', () => {
    expect(getLocationName(mockLocationMultiple)).toBe(
      '🇺🇸 United States, California, Los Angeles | 🇨🇦 Canada, Ontario, Toronto',
    );
    expect(getLocationName(mockLocationSingle)).toBe(
      '🇺🇸 United States, California, Los Angeles',
    );
    expect(getLocationName(mockLocationMultipleMinimal)).toBe(
      '🇪🇸 Spain | 🇨🇦 Canada, Ontario, Toronto',
    );
  });

  it.each([
    [true, 'https://gtfs.translink.ca/v2/gtfsposition'],
    [false, 'gtfs.translink.ca/v2/gtfsposition'],
    [true, 'http://whistler.mapstrat.com/current/gtfrealtime_TripUpdates.bin'],
    [true, 'http://gtfs.halifax.ca/realtime/Vehicle/VehiclePositions.pb'],
    [true, 'http://api.tampa.onebusaway.org:8088/trip-updates'],
    [true, 'https://example.com/feeds/gtfs.zip'],
    [false, '//example.com/feeds/'],
    [
      true,
      'https://ckan.pbh.gov.br/dataset/77764a7e-63fc-4111-ace3-fb7d3037953a/resource/f0fa78dc-74c3-49fa-8971-c310a76a07fa/download/gtfsfiles.zip',
    ],
    [true, 'HTTP://gtfs.translink.ca/v2/gtfsposition'],
    [false, 'http://.'],
    [false, ''],
  ])('should retrun %s when input is %s', (expected, input) => {
    expect(isValidFeedLink(input)).toBe(expected);
  });
});
