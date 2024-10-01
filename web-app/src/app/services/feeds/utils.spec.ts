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

  it('should validate feed links correctly', () => {
    const link1 = 'https://gtfs.translink.ca/v2/gtfsposition';
    expect(isValidFeedLink(link1)).toBe(true);

    const link2 = 'gtfs.translink.ca/v2/gtfsposition';
    expect(isValidFeedLink(link2)).toBe(false);

    const link3 =
      'http://whistler.mapstrat.com/current/gtfrealtime_TripUpdates.bin';
    expect(isValidFeedLink(link3)).toBe(true);

    const link4 = 'http://gtfs.halifax.ca/realtime/Vehicle/VehiclePositions.pb';
    expect(isValidFeedLink(link4)).toBe(true);

    const link5 = 'http://api.tampa.onebusaway.org:8088/trip-updates';
    expect(isValidFeedLink(link5)).toBe(true);

    const link6 =
      'https://transitfeeds.com/p/via-metropolitan-transit/62/latest/download';
    expect(isValidFeedLink(link6)).toBe(true);

    const link7 = '//transitfeeds.com/p/';
    expect(isValidFeedLink(link7)).toBe(false);

    const link8 =
      'https://ckan.pbh.gov.br/dataset/77764a7e-63fc-4111-ace3-fb7d3037953a/resource/f0fa78dc-74c3-49fa-8971-c310a76a07fa/download/gtfsfiles.zip';
    expect(isValidFeedLink(link8)).toBe(true);

    const link9 = 'HTTP://gtfs.translink.ca/v2/gtfsposition';
    expect(isValidFeedLink(link9)).toBe(true);

    expect(isValidFeedLink('')).toBe(false);
  });
});
