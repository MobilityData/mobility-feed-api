import { styled, Typography } from '@mui/material';
import { fontFamily } from '../Theme';

export const SearchHeader = styled(Typography)(({ theme }) => ({
  fontWeight: 'bold',
  fontFamily: fontFamily.secondary,
  '&.no-collapse': {
    margin: '12px 0 0',
  },
  '&:not(:first-of-type)': {
    marginTop: theme.spacing(1),
  },
  '&:after': {
    content: '""',
    display: 'block',
    height: '2px',
    width: '104px',
    background: theme.palette.text.primary,
  },
}));
