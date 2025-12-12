import {
  type AllFeedType,
  type GBFSFeedType,
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';

/**
 * Structured data is purely for SEO purposes.
 * It helps search engines understand the content of the page better.
 * It is not used in the application logic.
 * It is not displayed to the user.
 */

type StructureDataInterface = Record<string, unknown>;

function getBasicStructuredData(
  feed: AllFeedType,
  description: string,
): StructureDataInterface {
  const dataTypeNaming =
    feed?.data_type === 'gtfs_rt' ? 'GTFS Realtime' : feed?.data_type;

  const structuredData: StructureDataInterface = {
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name: `${dataTypeNaming ?? ''} Feed for ${feed?.provider}`,
    description,
    url: `https://mobilitydatabase.org/feeds/${feed?.data_type}/${feed?.id}`,
    license: feed?.source_info?.license_url,
    creator: {
      '@type': 'Organization',
      name: feed?.provider,
    },
    provider: {
      '@type': 'Organization',
      name: 'MobilityData',
      url: 'https://mobilitydata.org/',
    },
  };
  return structuredData;
}

function generateLocationStructuredData(
  feed: GTFSFeedType | GBFSFeedType,
  bb: {
    minimum_latitude?: number;
    minimum_longitude?: number;
    maximum_latitude?: number;
    maximum_longitude?: number;
  },
): StructureDataInterface {
  const municipalities =
    feed?.locations
      ?.map((location) => location.municipality)
      .filter((municipality) => municipality !== undefined) ?? [];
  const name =
    municipalities.length > 0
      ? `${municipalities.slice(0, 3).join(', ')}${
          municipalities.length > 3 ? ', and others' : ''
        }`
      : 'Transit coverage area';
  return {
    '@type': 'Place',
    name,
    geo: {
      '@type': 'GeoShape',
      box: `${bb.minimum_latitude} ${bb.minimum_longitude} ${bb.maximum_latitude} ${bb.maximum_longitude}`,
    },
  };
}

function getGtfsStructuredData(
  feed: GTFSFeedType,
  description: string,
): StructureDataInterface {
  const structuredGtfsData: StructureDataInterface = {
    ...getBasicStructuredData(feed, description),
    identifier: feed?.id,
    keywords: [
      'gtfs',
      'data',
      'public transit',
      'schedule data',
      'transportation',
    ],
    distribution: {
      '@type': 'DataDownload',
      encodingFormat: 'application/zip',
      contentUrl: feed?.latest_dataset?.hosted_url,
    },

    dateModified: feed?.latest_dataset?.downloaded_at ?? feed?.created_at,
  };

  if (feed?.latest_dataset?.hosted_url != null) {
    structuredGtfsData.distribution = {
      '@type': 'DataDownload',
      encodingFormat: 'application/zip',
      contentUrl: feed?.latest_dataset?.hosted_url,
    };
  }

  if (feed?.latest_dataset?.bounding_box != null) {
    structuredGtfsData.spatialCoverage = generateLocationStructuredData(
      feed,
      feed?.latest_dataset?.bounding_box,
    );
  }

  if (feed?.latest_dataset?.validation_report?.features != null) {
    structuredGtfsData.variableMeasured =
      feed.latest_dataset.validation_report.features.map((feature) => ({
        '@type': 'PropertyValue',
        name: feature,
      }));
  }

  return structuredGtfsData;
}

function getGbfsStructuredData(
  feed: GBFSFeedType,
  description: string,
): StructureDataInterface {
  const structuredGbfsData: StructureDataInterface = {
    ...getBasicStructuredData(feed, description),
    identifier: feed?.system_id,
    keywords: [
      'GBFS',
      'shared mobility',
      'micromobility',
      'bike share',
      'scooter share',
      'real-time data',
    ],
    creator: {
      '@type': 'Organization',
      name: feed?.provider,
      url: feed?.provider_url,
    },
    spatialCoverage: feed?.locations?.map((location) => ({
      '@type': 'Place',
      name: 'Location for ' + feed?.provider,
      address: {
        '@type': 'PostalAddress',
        addressLocality: location.municipality,
        addressRegion: location.subdivision_name,
        addressCountry: location.country_code,
      },
    })),
    dateModified: feed?.versions?.[0]?.created_at ?? feed?.created_at,
  };

  if (feed?.versions != null && feed?.versions.length > 0) {
    structuredGbfsData.hasPart = feed.versions.map((version) => ({
      '@type': 'DataFeed',
      name:
        `GBFS ${version.version} Feed` +
        (version.source === 'autodiscovery' ? ' - Autodiscovery Url' : ''),
      url: version.endpoints?.find((endpoint) => endpoint.name === 'gbfs')?.url,
      encodingFormat: 'application/json',
    }));
  }

  return structuredGbfsData;
}

function getGtfsRtStructuredData(
  feed: GTFSRTFeedType,
  description: string,
  relatedFeeds?: AllFeedType[],
  relatedGtfsFeeds?: GTFSRTFeedType[],
): StructureDataInterface {
  const associatedGtfsFeed: GTFSFeedType = relatedFeeds?.find(
    (relatedFeed) => relatedFeed?.data_type === 'gtfs',
  );

  const structuredGtfsRtData: StructureDataInterface = {
    ...getBasicStructuredData(feed, description),
    identifier: feed?.id,
    keywords: [
      'GTFS Realtime',
      'public transit',
      'real-time data',
      'trip updates',
      'vehicle positions',
      'service alerts',
    ],
    distribution: {
      '@type': 'DataDownload',
      encodingFormat: 'application/x-protobuf',
      contentUrl: feed?.source_info?.producer_url,
    },
    dateModified: feed?.created_at,
    hasPart: [],
  };

  if (associatedGtfsFeed?.latest_dataset?.bounding_box != null) {
    structuredGtfsRtData.spatialCoverage = generateLocationStructuredData(
      feed,
      associatedGtfsFeed?.latest_dataset?.bounding_box,
    );
  }

  if (associatedGtfsFeed != null) {
    (structuredGtfsRtData.hasPart as unknown[]).push({
      '@type': 'Dataset',
      name: `GTFS Static Feed for ${feed?.provider}`,
      url: `https://mobilitydatabase.org/feeds/gtfs/${associatedGtfsFeed.id}`,
      distribution: {
        '@type': 'DataDownload',
        encodingFormat: 'application/zip',
        contentUrl: associatedGtfsFeed.source_info?.producer_url,
      },
    });
  }
  if (relatedGtfsFeeds != null && relatedGtfsFeeds.length > 0) {
    relatedGtfsFeeds.forEach((relatedFeed) => {
      let name = `GTFS Realtime Feed for ${relatedFeed?.provider}`;

      if (relatedFeed?.entity_types != null) {
        if (relatedFeed.entity_types.includes('sa')) {
          name = `GTFS Realtime Service Alerts for ${relatedFeed?.provider}`;
        } else if (relatedFeed.entity_types.includes('tu')) {
          name = `GTFS Realtime Trip Updates for ${relatedFeed?.provider}`;
        } else if (relatedFeed.entity_types.includes('vp')) {
          name = `GTFS Realtime Vehicle Positions for ${relatedFeed?.provider}`;
        }
      }

      (structuredGtfsRtData.hasPart as unknown[]).push({
        '@type': 'Dataset',
        name,
        url: `https://mobilitydatabase.org/feeds/gtfs_rt/${relatedFeed?.id}`,
        distribution: {
          '@type': 'DataDownload',
          encodingFormat: 'application/x-protobuf',
          contentUrl: relatedFeed?.source_info?.producer_url,
        },
      });
    });
  }

  return structuredGtfsRtData;
}

export default function generateFeedStructuredData(
  feed: AllFeedType,
  description: string,
  // For gtfs rt
  relatedFeeds?: AllFeedType[],
  relatedGtfsFeeds?: GTFSFeedType[],
): StructureDataInterface | undefined {
  let structuredData: StructureDataInterface | undefined;
  if (feed?.data_type === 'gtfs') {
    structuredData = getGtfsStructuredData(feed as GTFSFeedType, description);
  } else if (feed?.data_type === 'gbfs') {
    structuredData = getGbfsStructuredData(feed as GBFSFeedType, description);
  } else if (feed?.data_type === 'gtfs_rt') {
    structuredData = getGtfsRtStructuredData(
      feed as GTFSRTFeedType,
      description,
      relatedFeeds,
      relatedGtfsFeeds,
    );
  }

  return structuredData;
}
