import * as React from 'react';
import { Box, Typography, colors } from '@mui/material';
import { ContentBox } from './ContentBox';
import { WarningAmberOutlined } from '@mui/icons-material';

export const WarningContentBox = (
  props: React.PropsWithChildren,
): React.ReactElement => {
  return (
    <ContentBox
      title={''}
      width={{ xs: '100%' }}
      outlineColor={colors.yellow[900]}
      padding={2}
      margin={'10px 0'}
    >
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <WarningAmberOutlined sx={{ mr: 1 }} />
        <Typography sx={{ fontWeight: 'bold' }}>{props.children}</Typography>
      </Box>
    </ContentBox>
  );
};
