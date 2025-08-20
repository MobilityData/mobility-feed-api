import { styled, Typography } from '@mui/material';

export const SearchHeader = styled(Typography)(({ theme }) => ({
  '&.no-collapse': {
    margin: '12px 0',
  },
  '&:not(:first-of-type)': {
    marginTop: theme.spacing(1),
  },
  '&:after': {
    content: '""',
    display: 'block',
    height: '3px',
    width: '104px',
    background: theme.palette.text.primary,
  },
}));
