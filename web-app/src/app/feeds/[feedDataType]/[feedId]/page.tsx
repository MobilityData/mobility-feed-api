import * as React from 'react';
import FeedView from '../../../screens/Feed/FeedView';
import {
  getFeed,
  getGtfsFeed,
  getGbfsFeed,
  getGtfsRtFeed,
  getGtfsFeedDatasets,
} from '../../../services/feeds';
import { notFound } from 'next/navigation';
import type { Metadata, ResolvingMetadata } from 'next';
import { getSSRAccessToken } from '../../../utils/auth-server';

type Props = {
  params: { feedDataType: string; feedId: string };
  searchParams: { [key: string]: string | string[] | undefined };
};

async function fetchFeedData(feedDataType: string, feedId: string) {
  const accessToken = await getSSRAccessToken(); // Token retrieved from cookie for SSR
  try {
    let feed = undefined;
    if (feedDataType === 'gtfs') {
      feed = await getGtfsFeed(feedId, accessToken);
    } else if (feedDataType === 'gtfs_rt') {
      feed = await getGtfsRtFeed(feedId, accessToken);
    } else if (feedDataType === 'gbfs') {
      feed = await getGbfsFeed(feedId, accessToken);
    } else {
      feed = await getFeed(feedId, accessToken);
    }
    return feed;
  } catch (e) {
    console.error('Error fetching feed', e);
    return undefined;
  }
}

async function fetchInitialDatasets(feedId: string) {
  const accessToken = await getSSRAccessToken();
  try {
    const datasets = await getGtfsFeedDatasets(feedId, accessToken, {
      limit: 10,
    });
    return datasets;
  } catch (e) {
    console.error('Error fetching initial datasets', e);
    return [];
  }
}

export async function generateMetadata(
  { params, searchParams }: Props,
  parent: ResolvingMetadata,
): Promise<Metadata> {
  const { feedId, feedDataType } = await params;
  const feed = await fetchFeedData(feedDataType, feedId);

  if (!feed) {
    return {
      title: 'Feed Not Found | Mobility Database',
    };
  }

  return {
    title: `${(feed as any).feed_name || feed.id} | Mobility Database`,
  };
}

export default async function FeedPage({ params }: Props) {
  const { feedId, feedDataType } = await params;
  console.log('feedId', feedId);
  console.log('feedDataType', feedDataType);

  let feedPromise = fetchFeedData(feedDataType, feedId);
  let datasetsPromise =
    feedDataType === 'gtfs'
      ? fetchInitialDatasets(feedId)
      : Promise.resolve([]);

  const [feed, initialDatasets] = await Promise.all([
    feedPromise,
    datasetsPromise,
  ]);

  if (!feed) {
    notFound();
  }

  return (
    <FeedView
      feed={feed}
      feedDataType={feedDataType}
      initialDatasets={initialDatasets}
    />
  );
}
