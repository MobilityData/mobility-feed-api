import { type PaletteColor, createTheme } from '@mui/material/styles';
import { type Property } from 'csstype';

declare module '@mui/material/Typography' {
  interface TypographyPropsVariantOverrides {
    sectionTitle: true;
  }
}

declare module '@mui/material/styles/createMixins' {
  // Allow for custom mixins to be added
  interface Mixins {
    code: Partial<PaletteColor> & {
      command: { fontWeight: Property.FontWeight; color: string };
    };
  }
}

export const fontFamily = {
  primary: '"Mulish"',
  secondary: '"IBM Plex Mono"',
};

const palette = {
  primary: {
    main: '#3959fa',
    dark: '#002eea',
    light: '#989ffc',
    contrastText: '#f9faff',
  },
  secondary: {
    main: '#96a1ff', // original mobility data purple
    dark: '#4a5fe8',
    light: '#e7e8ff',
    contrastText: '#f9faff',
  },
  background: {
    default: '#ffffff',
    paper: '#F8F5F5',
  },
  text: {
    primary: '#474747',
    secondary: 'rgba(71, 71, 71, 0.8)',
    disabled: 'rgba(0,0,0,0.3)',
  },
};

export const theme = createTheme({
  palette,
  mixins: {
    code: {
      contrastText: '#f1fa8c',
      command: {
        fontWeight: 'bold',
        color: '#ff79c6',
      },
    },
  },
  typography: {
    fontFamily: fontFamily.primary,
  },
  components: {
    MuiFormLabel: {
      styleOverrides: {
        root: {
          color: '#474747',
          fontWeight: 'bold',
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '&.md-small-input': {
            input: { paddingTop: '7px', paddingBottom: '7px' },
          },
        },
      },
    },
    MuiSelect: {
      styleOverrides: {
        root: {
          '.MuiSelect-select': { paddingTop: '7px', paddingBottom: '7px' },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          boxShadow: 'none',
          fontFamily: fontFamily.secondary,
          boxSizing: 'border-box',
          '&.MuiButton-contained': {
            border: '2px solid transparent',
          },
          '&.MuiButton-containedPrimary:hover': {
            boxShadow: 'none',
            backgroundColor: 'transparent',
            border: `2px solid ${palette.primary.main}`,
            color: palette.primary.main,
          },
          '&.MuiButton-outlinedPrimary': {
            border: `2px solid ${palette.primary.main}`,
            padding: '6px 16px',
          },
          '&.MuiButton-outlinedPrimary:hover': {
            backgroundColor: palette.primary.main,
            color: palette.primary.contrastText,
          },
        },
      },
    },
    MuiTypography: {
      variants: [
        {
          props: { variant: 'sectionTitle' },
          style: {
            color: palette.primary?.main,
            fontWeight: 'bold',
            fontSize: '1.5rem',
            marginBottom: '0.5rem',
            marginTop: '1rem',
          },
        },
      ],
    },
  },
});
