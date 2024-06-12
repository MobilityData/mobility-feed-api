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

export default function SearchResultItem({
  result,
}: SearchResultItemProps): React.ReactElement {
  if (result === undefined) return <></>;
  return (
    <ContentBox
      key={result.id}
      title={result.provider ?? ''}
      width={{ xs: '80%' }}
      outlineColor={colors.blue[900]}
    >
      <Grid container>
        <Grid item>
          <div>
            {result?.locations !== undefined
              ? Object.values(result?.locations[0])
                  .filter((v) => v !== null)
                  .reverse()
                  .join(', ')
              : ''}
          </div>
        </Grid>
        <Grid item>
          <div>
            <Chip label={`Deprecated`} color='error' variant='outlined' />
            <Chip label={`GTFS Schedule`} color='primary' variant='outlined' />
            <Chip label={`GTFS Schedule`} variant='outlined' />
          </div>
        </Grid>
      </Grid>
    </ContentBox>
  );
}
