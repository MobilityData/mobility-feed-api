import { Box, styled, type SxProps, type Theme } from '@mui/material';

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

export const featureChipsStyle: SxProps<Theme> = (theme) => ({
  color: theme.palette.primary.contrastText,
  backgroundColor: theme.palette.secondary.dark,
  border: `2px solid transparent`,
  ':hover': {
    opacity: 0.95,
  },
});

export const mapBoxPositionStyle = {
  position: 'relative',
  width: 'calc(100% + 32px)',
  flexGrow: 1,
  mb: '-16px',
  mx: '-16px',
};

export const boxElementStyle: SxProps = {
  width: '100%',
  mt: 2,
  mb: 1,
};

export const boxElementStyleTransitProvider: SxProps = {
  width: '100%',
  mt: 2,
  borderBottom: 'none',
};

export const boxElementStyleProducerURL: SxProps = {
  width: '100%',
  mb: 1,
};

export const StyledTitleContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  gap: theme.spacing(1),
  marginBottom: '4px',
  marginTop: theme.spacing(3),
  alignItems: 'center',
}));

export const StyledListItem = styled('li')(({ theme }) => ({
  width: '100%',
  margin: '5px 0',
  fontWeight: 'normal',
  fontSize: '16px',
}))

export const ResponsiveListItem = styled(StyledListItem)(({ theme }) => ({
  [theme.breakpoints.up('lg')]: {
    width: 'calc(50% - 15px)',
  },
}));
