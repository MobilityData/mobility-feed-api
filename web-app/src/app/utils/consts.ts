export class DATASET_FEATURES_FILES_MAPPING {
  private constructor(
    public readonly variable: string,
    public readonly displayName: string,
  ) {}

  public static getFeedFileByFeatureName(variable: string): string | undefined {
    const mapping = Object.values(DATASET_FEATURES_FILES_MAPPING).find(
      (mapping) => mapping.variable.toLowerCase() === variable.toLowerCase(),
    );
    return mapping?.displayName;
  }

  public static readonly faresV1 = new DATASET_FEATURES_FILES_MAPPING(
    'Fares V1',
    'fare_attributes.txt',
  );

  public static readonly textToSpeech = new DATASET_FEATURES_FILES_MAPPING(
    'Text-to-speech',
    'stops.txt - tts_stop_name',
  );

  public static readonly wheelchairAccessibilityTrips =
    new DATASET_FEATURES_FILES_MAPPING(
      'Wheelchair accessibility',
      'trips.txt - wheelchair_accessible',
    );

  public static readonly wheelchairAccessibilityStops =
    new DATASET_FEATURES_FILES_MAPPING(
      'Wheelchair accessibility',
      'stops.txt - wheelchair_boarding',
    );

  public static readonly routeColorsColor = new DATASET_FEATURES_FILES_MAPPING(
    'Route colors',
    'routes.txt - color',
  );

  public static readonly routeColorsRouteColor =
    new DATASET_FEATURES_FILES_MAPPING(
      'Route colors',
      'routes.txt - route_color',
    );

  public static readonly bikesAllowed = new DATASET_FEATURES_FILES_MAPPING(
    'Bikes Allowed',
    'trips.txt - bikes_allowed',
  );

  public static readonly translations = new DATASET_FEATURES_FILES_MAPPING(
    'Translations',
    'translations.txt',
  );

  public static readonly headsignsTrips = new DATASET_FEATURES_FILES_MAPPING(
    'Headsigns',
    'trips.txt - trip_headsign',
  );

  public static readonly headsignsStopTimes =
    new DATASET_FEATURES_FILES_MAPPING(
      'Headsigns',
      'stop_times.txt - stop_headsign',
    );

  public static readonly fareProducts = new DATASET_FEATURES_FILES_MAPPING(
    'Fare Products',
    'fare_products.txt',
  );

  public static readonly fareMedia = new DATASET_FEATURES_FILES_MAPPING(
    'Fare Media',
    'fare_media.txt',
  );

  public static readonly routeBasedFaresRoutes =
    new DATASET_FEATURES_FILES_MAPPING(
      'Route-Based Fares',
      'routes.txt - network_id',
    );

  public static readonly routeBasedFaresNetworks =
    new DATASET_FEATURES_FILES_MAPPING('Route-Based Fares', 'networks.txt');

  public static readonly timeBasedFares = new DATASET_FEATURES_FILES_MAPPING(
    'Time-Based Fares',
    'timeframes.txt',
  );

  public static readonly zoneBasedFares = new DATASET_FEATURES_FILES_MAPPING(
    'Zone-Based Fares',
    'areas.txt',
  );

  public static readonly transferFares = new DATASET_FEATURES_FILES_MAPPING(
    'Transfer Fares',
    'fare_transfer_rules.txt',
  );

  public static readonly pathwaysBasic = new DATASET_FEATURES_FILES_MAPPING(
    'Pathways (basic)',
    'pathways.txt',
  );

  public static readonly pathwaysExtra = new DATASET_FEATURES_FILES_MAPPING(
    'Pathways (extra)',
    'pathways.txt - max_slope or max_width or length or stair_count',
  );

  public static readonly levels = new DATASET_FEATURES_FILES_MAPPING(
    'Levels',
    'levels.txt',
  );

  public static readonly inStationTraversalTime =
    new DATASET_FEATURES_FILES_MAPPING(
      'In-station traversal time',
      'pathways.txt - traversal_time',
    );

  public static readonly pathwaysDirections =
    new DATASET_FEATURES_FILES_MAPPING(
      'Pathways directions',
      'pathways.txt - signposted_as or reverse_signposted_as',
    );

  public static readonly locationTypes = new DATASET_FEATURES_FILES_MAPPING(
    'Location types',
    'stops.txt - location_type',
  );

  public static readonly feedInformation = new DATASET_FEATURES_FILES_MAPPING(
    'Feed Information',
    'feed_info.txt',
  );

  public static readonly attributions = new DATASET_FEATURES_FILES_MAPPING(
    'Attributions',
    'attributions.txt',
  );

  public static readonly continuousStopsRoutes =
    new DATASET_FEATURES_FILES_MAPPING(
      'Continuous Stops',
      'routes.txt - continuous_drop_off or continuous_pickup',
    );

  public static readonly continuousStopsStopTimes =
    new DATASET_FEATURES_FILES_MAPPING(
      'Continuous Stops',
      'stop_times.txt - continuous_drop_off or continuous_pickup',
    );

  public static readonly shapes = new DATASET_FEATURES_FILES_MAPPING(
    'Shapes',
    'shapes.txt',
  );

  public static readonly transfers = new DATASET_FEATURES_FILES_MAPPING(
    'Transfers',
    'transfers.txt',
  );

  public static readonly frequencies = new DATASET_FEATURES_FILES_MAPPING(
    'Frequencies',
    'frequencies.txt',
  );
}
