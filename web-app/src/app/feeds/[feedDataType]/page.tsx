/**
 *  This route is a small hack to accomodate the route '/feeds/[feedId]/page.tsx'
 *  Although the parameter is 'feedDataType', the actual parameter used is 'feedId'
 *  This url is for backwards compatibility, is used more internally and is not an optimal way to access the feed detail page
 *  IMPORTANT: This url structure will need to be reviewed in the future once our urls could contain agencies
 */

import { type JSX } from 'react';
import { getFeed } from '../../services/feeds';
import { getSSRAccessToken } from '../../utils/auth-server';
import { notFound, redirect } from 'next/navigation';

interface Props {
  params: Promise<{ feedDataType: string }>;
}

export default async function Page({ params }: Props): Promise<JSX.Element> {
  const { feedDataType } = await params;
  const accessToken = await getSSRAccessToken();

  // IMPORTANT: here feedDataType is actually feedId (due to routing hack)
  const feedId = feedDataType;
  const feed = await getFeed(feedId, accessToken);

  if (feed == undefined) {
    notFound();
  }

  redirect(`/feeds/${feed.data_type}/${feedId}`);
}
