import { generatePmtilesUrls } from './GtfsVisualizationMap.functions';

describe('generatePmtilesUrls', () => {
  const latestDataset = {
    hosted_url:
      'https://files.mobilitydatabase.org/mdb-437/mdb-437-202511031503/mdb-437-202511031503.zip',
  };

  const latestDatasetJbda = {
    hosted_url:
      'https://files.mobilitydatabase.org/jbda-4371/jbda-4371-202511050124/jbda-4371-202511031503.zip',
  };

  it('should generate correct PMTiles URLs when given valid dataset and visualizationId', () => {
    const result = generatePmtilesUrls(latestDataset, 'mdb-120-202511060901');

    expect(result).toEqual({
      stopsPmtilesUrl:
        'https://files.mobilitydatabase.org/mdb-437/mdb-120-202511060901/pmtiles/stops.pmtiles',
      routesPmtilesUrl:
        'https://files.mobilitydatabase.org/mdb-437/mdb-120-202511060901/pmtiles/routes.pmtiles',
    });
  });

  it('should return URLs with different system ids', () => {
    const result = generatePmtilesUrls(
      latestDatasetJbda,
      'jbda-120-202511060901',
    );
    expect(result.stopsPmtilesUrl).toContain(
      'https://files.mobilitydatabase.org/jbda-4371/jbda-120-202511060901/pmtiles/stops.pmtiles',
    );
  });

  it('should handle undefined dataset gracefully', () => {
    const result = generatePmtilesUrls(undefined, 'jbda-120-202511060901');

    expect(result).toEqual({
      stopsPmtilesUrl: 'pmtiles/stops.pmtiles',
      routesPmtilesUrl: 'pmtiles/routes.pmtiles',
    });
  });

  it('should handle empty visualizationId', () => {
    const result = generatePmtilesUrls(latestDataset, '');

    expect(result.stopsPmtilesUrl).toContain('pmtiles/stops.pmtiles');
    expect(result.routesPmtilesUrl).toContain('pmtiles/routes.pmtiles');
  });
});
