import { styled, Typography } from '@mui/material';

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
