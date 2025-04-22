import { type SxProps, type Theme } from '@mui/material';

export const feedDetailContentContainerStyle = (props: {
  theme: Theme;
  isGtfsRT: boolean;
}): SxProps => {
  return {
    width: '100%',
    display: 'flex',
    flexDirection: {
      xs: props.isGtfsRT ? 'column' : 'column-reverse',
      md: props.isGtfsRT ? 'row' : 'row-reverse',
    },
    gap: 3,
    flexWrap: 'nowrap',
    justifyContent: 'space-between',
    mb: 4,
  };
};

export const ctaContainerStyle: SxProps<Theme> = (theme) => ({
  my: 3,
  width: '100%',
  display: 'flex',
  gap: 1,
  borderTop: `1px solid ${theme.palette.divider}`,
  pt: 3,
});

export const mapBoxPositionStyle = {
  width: 'calc(100% + 32px)',
  flexGrow: 1,
  mb: '-16px',
  mx: '-16px',
};
