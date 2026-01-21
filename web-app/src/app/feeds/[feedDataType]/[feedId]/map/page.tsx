import FullMapView from '../../../../screens/Feed/components/FullMapView';
import { type ReactElement } from 'react';

export default function FullMapViewPage(): ReactElement {
  // TODO: room for improvement: pass necessary props instead of fetching inside
  // Also think of a way to manage data if gotten from the previous page
  return <FullMapView />;
}
