import { type Theme } from '@mui/material';
import { type SystemStyleObject } from '@mui/system';

export const verificationBadgeStyle = (
  theme: Theme,
): SystemStyleObject<Theme> => ({
  background: `linear-gradient(25deg, ${theme.palette.primary.light}, ${theme.palette.primary.dark})`,
  color: 'white',
});
