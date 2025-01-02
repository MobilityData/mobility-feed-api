import { styled, type SxProps, Typography } from '@mui/material';

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

export const stickyHeaderStyle: SxProps = {
  boxShadow: '0 6px 22px rgba(15,39,65,.1),0 5px 20px rgba(57,89,250,.08)',
};
