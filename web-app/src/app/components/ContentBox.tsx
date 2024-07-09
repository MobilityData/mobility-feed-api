import * as React from 'react';
import { Box, Grid } from '@mui/material';

export interface ContentBoxProps {
  title: string;
  width: Record<string, string>;
  outlineColor: string;
  padding?: string | number;
}

export const ContentBox = (
  props: React.PropsWithChildren<ContentBoxProps>,
): JSX.Element => {
  return (
    <Box
      width={props.width}
      sx={{
        background: '#FFFFFF',
        borderRadius: '6px',
        border: `2px solid ${props.outlineColor}`,
        p: props.padding ?? 5,
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
