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

const palette = {
  primary: {
    main: '#3959fa',
    contrastText: '#f9faff',
  },
  secondary: {
    main: '#96a1ff',
  },
  background: {
    default: '#ffffff',
    paper: '#f7f7f7',
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
    fontFamily: '"Muli"',
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
