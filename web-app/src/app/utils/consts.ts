interface DatasetFeature {
  component: string;
  fileName: string;
  linkToInfo: string;
}

type DatasetFeatures = Record<string, DatasetFeature>;

export function getDataFeatureUrl(feature: string): string {
  return (
    DATASET_FEATURES[feature]?.linkToInfo ??
    DATASET_FEATURES['overview'].linkToInfo
  );
}

export const DATASET_FEATURES: DatasetFeatures = {
  overview: {
    component: '',
    fileName: '',
    linkToInfo: 'https://gtfs.org/getting_started/features/overview/',
  },
  'Text-To-Speech': {
    component: 'Accessibility',
    fileName: 'stops.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/accessibility/#text-to-speech',
  },
  'Stops Wheelchair Accessibility': {
    component: 'Accessibility',
    fileName: 'trips.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/accessibility/#stops-wheelchair-accessibility',
  },
  'Trips Wheelchair Accessibility': {
    component: 'Accessibility',
    fileName: 'trips.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/accessibility/#trips-wheelchair-accessibility',
  },
  'Route Colors': {
    component: 'Base add-ons',
    fileName: 'routes.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#route-colors',
  },
  'Bike Allowed': {
    component: 'Base add-ons',
    fileName: 'trips.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#bike-allowed',
  },
  Translations: {
    component: 'Base add-ons',
    fileName: 'translations.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#translations',
  },
  Headsigns: {
    component: 'Base add-ons',
    fileName: 'trips.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#headsigns',
  },
  'Fare Products': {
    component: 'Fares',
    fileName: 'fare_products.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/fares/#fare-products',
  },
  'Fare Media': {
    component: 'Fares',
    fileName: 'fare_media.txt',
    linkToInfo: 'https://gtfs.org/getting_started/features/fares/#fare-media',
  },
  'Route-Based Fares': {
    component: 'Fares',
    fileName: 'routes.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/fares/#route-based-fares',
  },
  'Time-Based Fares': {
    component: 'Fares',
    fileName: 'timeframes.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/fares/#time-based-fares',
  },
  'Zone-Based Fares': {
    component: 'Fares',
    fileName: 'areas.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/fares/#zone-based-fares',
  },
  'Fare Transfers': {
    component: 'Fares',
    fileName: 'fare_transfer_rules.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/fares/#fare-transfers',
  },
  'Fares V1': {
    component: 'Fares',
    fileName: 'fare_attributes.txt',
    linkToInfo: 'https://gtfs.org/getting_started/features/fares/#fares-v1',
  },
  'Pathway Connections': {
    component: 'Pathways',
    fileName: 'pathways.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/pathways/#pathway-connections',
  },
  'Pathway Details': {
    component: 'Pathways',
    fileName: 'pathways.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/pathways/#pathway-details',
  },
  Levels: {
    component: 'Pathways',
    fileName: 'levels.txt',
    linkToInfo: 'https://gtfs.org/getting_started/features/pathways/#levels',
  },
  'In-station traversal time': {
    component: 'Pathways',
    fileName: 'pathways.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/pathways/#in-station-traversal-time',
  },
  'Pathway Signs': {
    component: 'Pathways',
    fileName: 'pathways.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/pathways/#pathway-signs',
  },
  'Location Types': {
    component: 'Base add-ons',
    fileName: 'stops.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#location-types',
  },
  'Feed Information': {
    component: 'Base add-ons',
    fileName: 'feed_info.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#feed-information',
  },
  Attributions: {
    component: 'Base add-ons',
    fileName: 'attributions.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#attributions',
  },
  'Continuous Stops': {
    component: 'Flexible Services',
    fileName: 'routes.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/flexible_services/#continuous-stops',
  },
  'Booking Rules': {
    component: 'Flexible Services',
    fileName: 'routes.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/flexible_services/#booking-rules',
  },
  'Fixed-Stops Demand Responsive Services': {
    component: 'Flexible Services',
    fileName: 'location_groups.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/flexible_services/#fixed-stops-demand-responsive-services',
  },
  'Zone-Based Demand Responsive Services': {
    component: 'Flexible Services',
    fileName: 'stop_times.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/flexible_services/#zone-based-demand-responsive-services',
  },
  'Predefined Routes with Deviation': {
    component: 'Flexible Services',
    fileName: 'stop_times.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/flexible_services/#predefined-routes-with-deviation',
  },
  Shapes: {
    component: 'Base add-ons',
    fileName: 'shapes.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#shapes ',
  },
  Transfers: {
    component: 'Base add-ons',
    fileName: 'transfers.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#transfers',
  },
  Frequencies: {
    component: 'Base add-ons',
    fileName: 'frequencies.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#frequency-based-service ',
  },
};

// DEPRECATED FEATURES
DATASET_FEATURES['Wheelchair Accessibility'] = {
  // as of 6.0
  component: 'Accessibility',
  fileName: 'trips.txt',
  linkToInfo: 'https://gtfs.org/getting_started/features/accessibility',
};
DATASET_FEATURES['Bikes Allowance'] = DATASET_FEATURES['Bike Allowed'];
DATASET_FEATURES['Transfer Fares'] = DATASET_FEATURES['Fare Transfers']; // as of 6.0
DATASET_FEATURES['Pathways (basic)'] = DATASET_FEATURES['Pathway Connections']; // as of 6.0
DATASET_FEATURES['Pathways (extra)'] = DATASET_FEATURES['Pathway Details']; // as of 6.0
DATASET_FEATURES['Traversal Time'] =
  DATASET_FEATURES['In-station traversal time'];
DATASET_FEATURES['Pathways Directions'] = {
  // as of 6.0
  component: 'Pathways',
  fileName: 'pathways.txt',
  linkToInfo: 'https://gtfs.org/schedule/reference/#pathwaystxt',
};
