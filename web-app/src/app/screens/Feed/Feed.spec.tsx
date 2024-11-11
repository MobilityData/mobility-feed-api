import { cleanup, render, screen } from '@testing-library/react';
import {
  formatProvidersSorted,
  generateDescriptionMetaTag,
  generatePageTitle,
  getFeedTitleElement,
} from '.';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import { type TFunction } from 'i18next';

const mockFeed: GTFSFeedType = {
  id: 'mdb-x',
  data_type: 'gtfs',
  status: 'active',
  created_at: undefined,
  external_ids: [
    {
      external_id: 'x',
      source: 'mdb',
    },
  ],
  provider: 'DPN, AVL, CFL, CFLBus, RGTR, TICE, TRAM',
  feed_name: 'Aggregated Luxembourg - OpenOV',
  note: '',
  feed_contact_email: '',
  source_info: {
    producer_url: 'http://fake.zip',
    authentication_type: 0,
    authentication_info_url: '',
    api_key_parameter_name: '',
    license_url: 'http://fake/LICENSE.TXT',
  },
  locations: [
    {
      country_code: 'BE',
    },
    {
      country_code: 'DE',
    },
    {
      country_code: 'FR',
    },
  ],
  latest_dataset: {
    id: '1',
    hosted_url: 'https://fake.zip',
    downloaded_at: '2024-07-03T17:38:24.963131Z',
    hash: 'x',
  },
};

const mockFeedOneProvider = {
  ...mockFeed,
  provider: 'AVL',
};

const mockFeedRT: GTFSRTFeedType = {
  id: 'mdb-x',
  data_type: 'gtfs_rt',
  status: 'active',
  external_ids: [
    {
      external_id: 'x',
      source: 'mdb',
    },
  ],
  provider:
    'SeaLink Pine Harbour, Waikato Regional Council, Pavlovich Transport Solutions, AT Metro',
  feed_name: 'Auckland Transport Developer',
  note: '',
  feed_contact_email: '',
  source_info: {
    producer_url: 'https://api.fake/vehiclelocations',
    authentication_type: 2,
    authentication_info_url: 'https://fake.govt.nz/',
    api_key_parameter_name: 'sub',
    license_url: 'https://fake/',
  },
  locations: [
    {
      country_code: 'NZ',
    },
  ],
  entity_types: ['vp'],
  feed_references: ['mdb-y'],
};

describe('Feed page', () => {
  afterEach(cleanup);

  it('should format the providers correctly', () => {
    const formattedProviders = formatProvidersSorted(mockFeed?.provider ?? '');
    expect(formattedProviders).toEqual([
      'AVL',
      'CFL',
      'CFLBus',
      'DPN',
      'RGTR',
      'TICE',
      'TRAM',
    ]);
  });

  it('should format the page title correctly when there are more than one and gtfs', () => {
    const mockT = jest.fn((key) => key) as unknown as TFunction<
      'feeds',
      undefined
    >;
    const formattedProviders = formatProvidersSorted(mockFeed?.provider ?? '');
    render(getFeedTitleElement(formattedProviders, mockFeed, mockT));
    expect(screen.getByText('AVL')).toBeTruthy();
    expect(screen.getByText('+6 common:others')).toBeTruthy();
  });

  it('should format the page title correctly when there are more than one and gtfs_rt', () => {
    const mockT = jest.fn((key) => key) as unknown as TFunction<
      'feeds',
      undefined
    >;
    const formattedProviders = formatProvidersSorted(
      mockFeedRT?.provider ?? '',
    );
    render(getFeedTitleElement(formattedProviders, mockFeedRT, mockT));
    expect(
      screen.getByText('AT Metro - Auckland Transport Developer'),
    ).toBeTruthy();
    expect(screen.getByText('+3 common:others')).toBeTruthy();
  });

  it('should format the page title correctly when there is only one provider', () => {
    const mockT = jest.fn((key) => key) as unknown as TFunction<
      'feeds',
      undefined
    >;
    const formattedProviders = formatProvidersSorted(
      mockFeedOneProvider?.provider ?? '',
    );
    render(getFeedTitleElement(formattedProviders, mockFeedOneProvider, mockT));
    expect(screen.getByText('AVL')).toBeTruthy();
    expect(screen.queryByText('+')).toBeNull();
  });

  it('should generate the correct page title', () => {
    const titleAllInfo = generatePageTitle(
      ['Department of Transport', 'Public Transport'],
      'gtfs',
      'Darwin public bus network',
    );
    expect(titleAllInfo).toEqual(
      'Department of Transport, Darwin public bus network gtfs schedule feed - Mobility Database',
    );

    const titleNoProviders = generatePageTitle(
      [],
      'gtfs',
      'Darwin public bus network',
    );
    expect(titleNoProviders).toEqual(
      'Darwin public bus network gtfs schedule feed - Mobility Database',
    );

    const titleNoName = generatePageTitle(
      ['Department of Transport', 'Public Transport'],
      'gtfs',
      '',
    );
    expect(titleNoName).toEqual(
      'Department of Transport gtfs schedule feed - Mobility Database',
    );

    const titleAllInfoRT = generatePageTitle(
      ['Department of Transport', 'Public Transport'],
      'gtfs_rt',
      'Darwin public bus network',
    );
    expect(titleAllInfoRT).toEqual(
      'Department of Transport, Darwin public bus network gtfs realtime feed - Mobility Database',
    );

    const titleAllEmpty = generatePageTitle([], 'gtfs', '');
    expect(titleAllEmpty).toEqual('Mobility Database');
  });

  it('should generate the correct page description', () => {
    const descriptionAllInfo = generateDescriptionMetaTag(
      ['Department of Transport', 'Public Transport'],
      'gtfs',
      'Darwin public bus network',
    );
    expect(descriptionAllInfo).toEqual(
      'Explore the Department of Transport, Darwin public bus network GTFS schedule feed details with access to a quality data insights',
    );

    const descriptionNoProviders = generateDescriptionMetaTag(
      [],
      'gtfs',
      'Darwin public bus network',
    );
    expect(descriptionNoProviders).toEqual(
      'Explore the Darwin public bus network GTFS schedule feed details with access to a quality data insights',
    );

    const descriptionNoName = generateDescriptionMetaTag(
      ['Department of Transport', 'Public Transport'],
      'gtfs',
      '',
    );
    expect(descriptionNoName).toEqual(
      'Explore the Department of Transport GTFS schedule feed details with access to a quality data insights',
    );

    const descriptionAllInfoRT = generateDescriptionMetaTag(
      ['Department of Transport', 'Public Transport'],
      'gtfs_rt',
      'Darwin public bus network',
    );
    expect(descriptionAllInfoRT).toEqual(
      'Explore the Department of Transport, Darwin public bus network GTFS realtime feed details with access to a quality data insights',
    );

    const descriptionAllEmpty = generateDescriptionMetaTag([], 'gtfs', '');
    expect(descriptionAllEmpty).toEqual('');
  });
});
