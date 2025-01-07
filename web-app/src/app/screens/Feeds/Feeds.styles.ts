import { styled, type SxProps, type Theme, Typography } from '@mui/material';

export const SearchHeader = styled(Typography)(({ theme }) => ({
  '&:not(:first-of-type)': {
    marginTop: theme.spacing(2),
  },
  '&:after': {
    content: '""',
    display: 'block',
    height: '3px',
    width: '104px',
    background: theme.palette.text.primary,
  },
}));

export const chipHolderStyles: SxProps<Theme> = (theme) => ({
  pdisplay: 'flex',
  flexWrap: 'wrap',
  gap: 1,
  minHeight: '31px',
  width: '100%',
  alignItems: 'center',
  mb: theme.spacing(1),
});

export const stickyHeaderStyles = (props: {
  theme: Theme;
  isSticky: boolean;
}): SxProps => {
  const styles: SxProps = {
    display: 'flex',
    alignItems: 'center',
    position: 'sticky',
    zIndex: 1,
    top: {
      xs: '56px',
      sm: '65px',
    },
    background: props.theme.palette.background.default,
    transition: 'box-shadow 0.3s ease-in-out',
    mx: {
      xs: '-16px',
      sm: '-24px',
    },
    py: 2,
  };
  if (props.isSticky) {
    styles.boxShadow =
      '0 6px 22px rgba(15,39,65,.1),0 5px 20px rgba(57,89,250,.08)';
  }
  return styles;
};

export const searchBarStyles: SxProps = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  boxSizing: 'content-box',
};
