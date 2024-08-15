import { getLocationName, type EntityLocations } from './utils';

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
});
