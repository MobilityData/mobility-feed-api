import { type SxProps, type Theme } from '@mui/material';
import { fontFamily } from '../Theme';

export const mobileNavElementStyle: SxProps<Theme> = (theme) => ({
  width: '100%',
  justifyContent: 'flex-start',
  pl: 3,
  color: theme.palette.text.primary,
});

export const animatedButtonStyling: SxProps<Theme> = (theme) => ({
  minWidth: 'fit-content',
  px: 0,
  mx: {
    md: 1,
    lg: 2,
  },
  fontFamily: fontFamily.secondary,
  '&:hover, &.active': {
    backgroundColor: 'transparent',
    '&::after': {
      transform: 'scaleX(1)',
      left: 0,
      right: 0,
      transformOrigin: 'left',
    },
  },
  '&.active.short': {
    '&::after': {
      right: '20px',
    },
  },
  '&::after': {
    content: '""',
    height: '2px',
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: theme.palette.primary.main,
    opacity: 0.7,
    transition: 'transform 0.9s cubic-bezier(0.19, 1, 0.22, 1)',
    transform: 'scaleX(0)',
    transformOrigin: 'right',
    pointerEvents: 'none',
  },
});
