import * as React from 'react';
import { Box, Grid, colors } from '@mui/material';

export interface ContentBoxProps {
  title: string;
}

export const ContentBox = (
  props: React.PropsWithChildren<ContentBoxProps>,
): JSX.Element => {
  return (
    <Box
      width={{ xs: '100%', md: '50%' }}
      sx={{
        background: '#FFFFFF',
        borderRadius: '6px',
        border: `2px solid ${colors.indigo[500]}`,
        p: 5,
        fontSize: '18px',
        fontWeight: 700,
        mr: 0,
      }}
    >
      <Grid
        container
        sx={{
          width: '100%',
        }}
      >
        <Grid item xs={12} fontSize={24}>
          {props.title}
        </Grid>
        {props.children}
      </Grid>
    </Box>
  );
};
