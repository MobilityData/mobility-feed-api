import { Box, Card, styled, Typography } from '@mui/material';

export const GroupCard = styled(Card)(({ theme }) => ({
  background: theme.palette.background.default,
  border: 'none',
  padding: theme.spacing(2),
  marginBottom: theme.spacing(2),
  '&:last-of-type': {
    marginBottom: 0,
  },
}));

export const GroupHeader = styled(Typography)(({ theme }) => ({
  display: 'flex',
  gap: theme.spacing(1),
  marginBottom: theme.spacing(1),
  alignItems: 'center',
  color: theme.palette.text.secondary,
}));

export const FeedLinkElement = styled(Box)(({ theme }) => ({
  width: 'calc(100% - 16px)',
  marginLeft: '16px',
  marginBottom: '16px',
  '&:last-child': {
    marginBottom: 0,
  },
}));
