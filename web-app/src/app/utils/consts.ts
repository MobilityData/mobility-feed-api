interface DatasetFeature {
  component: string;
  fileName: string;
  linkToInfo: string;
}

type DatasetFeatures = Record<string, DatasetFeature>;

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
  'Wheelchair Accessibility': {
    component: 'Accessibility',
    fileName: 'trips.txt',
    linkToInfo: 'https://gtfs.org/getting_started/features/accessibility',
  },
  'Route Colors': {
    component: 'Accessibility',
    fileName: 'routes.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#route-colors',
  },
  'Bikes Allowance': {
    component: 'Accessibility',
    fileName: 'trips.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#bike-allowed',
  },
  Translations: {
    component: 'Accessibility',
    fileName: 'translations.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#translations',
  },
  Headsigns: {
    component: 'Accessibility',
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
  'Transfer Fares': {
    component: 'Fares',
    fileName: 'fare_transfer_rules.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/fares/#fares-transfers',
  },
  'Fares V1': {
    component: 'Fares',
    fileName: 'fare_attributes.txt',
    linkToInfo: 'https://gtfs.org/getting_started/features/fares/#fares-v1',
  },
  'Pathways (basic)': {
    component: 'Pathways',
    fileName: 'pathways.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/pathways/#pathway-connections',
  },
  'Pathways (extra)': {
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
  'Traversal Time': {
    component: 'Pathways',
    fileName: 'pathways.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/pathways/#in-station-traversal-time',
  },
  'Pathways Directions': {
    component: 'Pathways',
    fileName: 'pathways.txt',
    linkToInfo: 'https://gtfs.org/schedule/reference/#pathwaystxt',
  },
  'Location Types': {
    component: 'Pathways',
    fileName: 'stops.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#location-types',
  },
  'Feed Information': {
    component: 'Metadata',
    fileName: 'feed_info.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#feed-information',
  },
  Attributions: {
    component: 'Metadata',
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
  Shapes: {
    component: 'Shapes',
    fileName: 'shapes.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#shapes ',
  },
  Transfers: {
    component: 'Transfers',
    fileName: 'transfers.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#transfers',
  },
  Frequencies: {
    component: 'Frequency-based Services',
    fileName: 'frequencies.txt',
    linkToInfo:
      'https://gtfs.org/getting_started/features/base_add-ons/#frequency-based-service ',
  },
};
