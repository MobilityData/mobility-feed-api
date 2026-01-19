import SearchTable, { getDataTypeElement } from './SearchTable';
import { render, cleanup, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { type AllFeedsType } from '../../services/feeds/utils';

const mockFeedsData: AllFeedsType = {
  total: 2004,
  results: [
    {
      id: '3',
      data_type: 'gtfs',
      status: 'active',
      created_at: undefined,
      external_ids: [
        {
          external_id: '170',
          source: 'mdb',
        },
      ],
      provider: 'Utah Transit Authority (UTA)',
      feed_name: '',
      note: '',
      feed_contact_email: '',
      source_info: {
        producer_url: 'https://fake/GTFS.zip',
        authentication_type: 0,
        authentication_info_url: '',
        api_key_parameter_name: '',
        license_url: 'http://fake/TermsOfUse.aspx',
      },
      redirects: undefined,
      locations: [
        {
          country_code: 'US',
          subdivision_name: 'Utah',
          municipality: undefined,
        },
      ],
      latest_dataset: {
        id: '1',
        hosted_url: 'fake.zip',
        bounding_box: undefined,
        downloaded_at: '2024-07-24T18:32:53.952458Z',
        hash: 'd',
        validation_report: undefined,
      },
      entity_types: undefined,
      feed_references: undefined,
    },
    {
      id: 'mdb-1003',
      data_type: 'gtfs',
      status: 'active',
      created_at: undefined,
      external_ids: [
        {
          external_id: '1003',
          source: 'mdb',
        },
      ],
      provider: 'TRAM',
      feed_name: '',
      note: '',
      feed_contact_email: '',
      source_info: {
        producer_url: 'https://fake/GTFS/zip/TBX.zip',
        authentication_type: 0,
        authentication_info_url: '',
        api_key_parameter_name: '',
        license_url: '',
      },
      redirects: undefined,
      locations: [
        {
          country_code: 'ES',
          subdivision_name: 'Catalonia',
          municipality: undefined,
        },
      ],
      latest_dataset: {
        id: '12',
        hosted_url: 'https://fa.zip',
        bounding_box: undefined,
        downloaded_at: '2024-07-24T18:38:29.574211Z',
        hash: 'g',
        validation_report: undefined,
      },
      entity_types: undefined,
      feed_references: undefined,
    },
    {
      id: 'g',
      data_type: 'gtfs',
      status: 'inactive',
      created_at: undefined,
      external_ids: [
        {
          external_id: '595',
          source: 'mdb',
        },
      ],
      provider:
        'Alcatraz Cruises - Hornblower, Angel Island Tiburon Ferry, Blue & Gold Fleet',
      feed_name: '',
      note: '',
      feed_contact_email: '',
      source_info: {
        producer_url: 'http://fakef.zip',
        authentication_type: 0,
        authentication_info_url: '',
        api_key_parameter_name: '',
        license_url: '',
      },
      redirects: undefined,
      locations: [
        {
          country_code: 'US',
          subdivision_name: 'California',
          municipality: 'San Francisco',
        },
      ],
      latest_dataset: {
        id: '24',
        hosted_url: 'https://fake.zip',
        bounding_box: undefined,
        downloaded_at: '2024-06-18T19:55:27.794061Z',
        hash: 'hg',
        validation_report: undefined,
      },
      entity_types: undefined,
      feed_references: undefined,
    },
  ],
};

describe.only('getProviderElement', () => {
  afterEach(cleanup);

  it('should display the correct number of transit providers in table row', () => {
    render(
      <MemoryRouter>
        <SearchTable feedsData={mockFeedsData} />
      </MemoryRouter>,
    );

    expect(screen.getByText('Utah Transit Authority (UTA)')).toBeTruthy();
    const parentElement = screen.getByText('Angel Island Tiburon Ferry');
    const spanElement = within(parentElement).getByText('+ 2', {
      selector: 'span',
    });
    expect(parentElement).toBeTruthy();
    expect(spanElement).toBeTruthy();
    expect(screen.queryByText('Alcatraz Cruises - Hornblower')).toBeNull();
  });

  it('should display the correct data type depending on the feed type', () => {
    const { getByText } = render(getDataTypeElement('gtfs'));
    expect(getByText('gtfsSchedule')).toBeInTheDocument();
  });

  it('should display the correct data type depending on the feed type', () => {
    const { getByText } = render(getDataTypeElement('gtfs_rt'));
    expect(getByText('gtfsRealtime')).toBeInTheDocument();
  });
});
