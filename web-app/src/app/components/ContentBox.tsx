import * as React from 'react';
import { Box, Typography, type SxProps } from '@mui/material';

export interface ContentBoxProps {
  title: string;
  width: Record<string, string>;
  outlineColor: string;
  padding?: Partial<SxProps>;
  margin?: string | number;
  sx?: SxProps;
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
        m: props.margin ?? 0,
        fontSize: '18px',
        fontWeight: 700,
        mr: 0,
        ...props.sx,
      }}
    >
      {props.title.trim() !== '' && (
        <Typography variant='h5' sx={{ flexShrink: 0, mb: 1 }}>
          {props.title}
        </Typography>
      )}
      {props.children}
    </Box>
  );
};
