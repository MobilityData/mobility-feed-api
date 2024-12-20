import { styled, Typography, type TypographyProps } from '@mui/material';

export const MainPageHeader = styled(Typography)<TypographyProps>({
  fontWeight: 700,
});

MainPageHeader.defaultProps = {
  variant: 'h4',
  color: 'primary',
  component: 'h1',
};
