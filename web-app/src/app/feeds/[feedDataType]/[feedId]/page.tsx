import * as React from 'react';
import FeedView from '../../../screens/Feed/FeedView';
import { generatePageTitle } from '../../../screens/Feed/Feed.functions';
import {
  getFeed,
  getGtfsFeed,
  getGbfsFeed,
  getGtfsRtFeed,
} from '../../../services/feeds';
import { notFound } from 'next/navigation';
import type { Metadata, ResolvingMetadata } from 'next';
import { getSSRAccessToken } from '../../../utils/auth-server';

// Mapping feedDataType to API calls
// Note: The original generic 'getFeed' might not be enough if we need specific types, but let's try to use the specific ones if possible.
// The URL structure is /feeds/[feedDataType]/[feedId]
// feedDataType can be 'gtfs', 'gtfs_rt', 'gbfs'

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
      // Fallback or specific generic feed call
      // feed = await getFeed(feedId, accessToken);
      // Note: getFeed uses /v1/feeds/{id} which might return any type.
      // Given the URL has dataType, we should probably prefer specific endpoints if the app Logic does.
      // However, `getFeed` is also available.
      feed = await getFeed(feedId, accessToken);
    }
    return feed;
  } catch (e) {
    console.error('Error fetching feed', e);
    return undefined;
  }
}

export async function generateMetadata(
  { params, searchParams }: Props,
  parent: ResolvingMetadata,
): Promise<Metadata> {
  const { feedId, feedDataType } = params;
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
  const feed = await fetchFeedData(feedDataType, feedId);

  if (!feed) {
    notFound();
  }

  // TODO: Fetch related feeds and datasets if needed for SSR, or let Client Wrapper fetch them?
  // User asked for SSR friendly. We should pass the feed data.
  // Related feeds might be a separate call.

  return <FeedView feed={feed} feedDataType={feedDataType} />;
}
