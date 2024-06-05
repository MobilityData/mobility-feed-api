import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  colors,
} from '@mui/material';
import { type components } from '../../services/feeds/types';

export interface FeaturesListProps {
  latestDataset: components['schemas']['GtfsDataset'] | undefined;
}

export default function FeaturesList({
  latestDataset,
}: FeaturesListProps): React.ReactElement {
  return (
    <ContentBox
      width={{ xs: '100%', md: '50%' }}
      title={'Features List'}
      outlineColor={colors.indigo[500]}
    >
      <TableContainer>
        <TableBody>
          {latestDataset?.validation_report?.features !== undefined &&
            latestDataset?.validation_report?.features?.length > 0 && (
              <TableRow>
                <TableCell>
                  <b>Feature</b>
                </TableCell>
              </TableRow>
            )}
          {latestDataset?.validation_report?.features?.map((v) => (
            <TableRow key={v}>
              <TableCell>{v}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </TableContainer>
    </ContentBox>
  );
}
