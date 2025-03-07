import { type SxProps, type Theme } from '@mui/material';

export const feedDetailContentContainerStyle = (props: {
  theme: Theme;
  isGtfsSchedule: boolean;
}): SxProps => {
  return {
    width: '100%',
    display: 'flex',
    flexDirection: {
      xs: props.isGtfsSchedule ? 'column-reverse' : 'column',
      md: props.isGtfsSchedule ? 'row-reverse' : 'row',
    },
    gap: 3,
    flexWrap: 'nowrap',
    justifyContent: 'space-between',
    mb: 4,
  };
};

export const ctaContainerStyle: SxProps<Theme> = (theme) => ({
  mb: 3,
  mt: 1,
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
