import * as React from 'react';
import { Chip, Grid, colors } from '@mui/material';
import { ContentBox } from '../../components/ContentBox';
import {
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';

export interface SearchResultItemProps {
  result: GTFSFeedType | GTFSRTFeedType;
}

const renderEntityTypeChip = (entityType: string): JSX.Element => {
  let label = 'Service Alerts';
  if (entityType === 'vp') {
    label = 'Vehicle Positions';
  } else if (entityType === 'tu') {
    label = 'Trip Updates';
  }
  return <Chip label={label} variant='outlined' />;
};

export default function SearchResultItem({
  result,
}: SearchResultItemProps): React.ReactElement {
  if (result === undefined) return <></>;
  return (
    <ContentBox
      key={result.id}
      title={
        result.provider?.substring(0, 100) +
          (result.provider?.length !== undefined &&
          result.provider?.length > 100
            ? '...'
            : '') ?? ''
      }
      width={{ xs: '100%' }}
      outlineColor={colors.blue[900]}
    >
      <Grid container>
        <Grid item xs={12}>
          <div>
            {result?.locations !== undefined
              ? Object.values(result?.locations[0])
                  .filter((v) => v !== null)
                  .reverse()
                  .join(', ')
              : ''}
          </div>
        </Grid>
        <Grid item xs={12}>
          {result.status === 'deprecated' && (
            <Chip label={`Deprecated`} color='error' variant='outlined' />
          )}
          {result.status === 'development' && (
            <Chip label={`Development`} color='error' variant='outlined' />
          )}
          <Chip
            label={
              result.data_type === 'gtfs' ? 'GTFS Schedule' : 'GTFS Realtime'
            }
            color='primary'
            variant='outlined'
          />
          {result.data_type === 'gtfs_rt' &&
            result.entity_types?.map((entityType) => {
              return renderEntityTypeChip(entityType);
            })}
        </Grid>
      </Grid>
    </ContentBox>
  );
}
