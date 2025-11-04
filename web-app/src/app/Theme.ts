import {
  type PaletteColor,
  type Theme,
  createTheme,
} from '@mui/material/styles';
import { type Property } from 'csstype';

declare module '@mui/material/styles' {
  interface Palette {
    boxShadow: string;
  }
  interface PaletteOptions {
    boxShadow?: string;
  }
  interface Theme {
    map: {
      basemapTileUrl: string;
      routeColor: string;
      routeTextColor: string;
    };
  }

  interface ThemeOptions {
    map?: {
      basemapTileUrl?: string;
      routeColor?: string;
      routeTextColor?: string;
    };
  }
}

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

export enum ThemeModeEnum {
  light = 'light',
  dark = 'dark',
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
  divider: 'rgba(0, 0, 0, 0.23)',
  boxShadow: '0px 1px 4px 2px rgba(0,0,0,0.2)',
};

const darkPalette = {
  primary: {
    main: '#96a1ff',
    dark: '#4a5dff',
    light: '#e7e8ff',
    contrastText: '#1D1717',
  },
  secondary: {
    main: '#3959fa',
    dark: '#002eea',
    light: '#989ffc',
    contrastText: '#ffffff',
  },
  background: {
    default: '#121212',
    paper: '#1E1E1E',
  },
  text: {
    primary: '#E3E3E3',
    secondary: 'rgba(255, 255, 255, 0.7)',
    disabled: 'rgba(255, 255, 255, 0.3)',
  },
  divider: 'rgba(255, 255, 255, 0.23)',
  boxShadow: '0px 1px 4px 2px rgba(0,0,0,0.6)',
};

export const getTheme = (mode: ThemeModeEnum): Theme => {
  const isLightMode = mode === ThemeModeEnum.light;
  const chosenPalette = !isLightMode ? darkPalette : palette;
  return createTheme({
    palette: { ...chosenPalette, mode },
    map: {
      basemapTileUrl: isLightMode
        ? 'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
        : 'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      routeColor: chosenPalette.background.default,
      routeTextColor: chosenPalette.text.primary,
    },
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
      MuiInputAdornment: {
        styleOverrides: {
          root: {
            color: 'inherit',
          },
        },
      },
      MuiFormLabel: {
        styleOverrides: {
          root: {
            color: chosenPalette.text.primary,
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
            '.MuiOutlinedInput-root fieldset': {
              borderColor: chosenPalette.divider,
            },
          },
        },
      },
      MuiSelect: {
        styleOverrides: {
          root: {
            '.MuiSelect-select': { paddingTop: '7px', paddingBottom: '7px' },
            '.MuiSvgIcon-root': { color: chosenPalette.text.primary },
            '&.MuiInputBase-root fieldset': {
              borderColor: chosenPalette.divider,
            },
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
              color: chosenPalette.background.default,
              '&.Mui-disabled': {
                backgroundColor: chosenPalette.text.disabled,
              },
            },
            '&.MuiButton-containedPrimary:hover': {
              boxShadow: 'none',
              backgroundColor: 'transparent',
              border: `2px solid ${chosenPalette.primary.main}`,
              color: chosenPalette.primary.main,
            },
            '&.MuiButton-outlinedPrimary': {
              border: `2px solid ${chosenPalette.primary.main}`,
              padding: '6px 16px',
            },
            '&.MuiButton-outlinedPrimary:hover': {
              backgroundColor: chosenPalette.primary.main,
              color: isLightMode
                ? chosenPalette.primary.contrastText
                : chosenPalette.background.default,
            },
            '&.MuiButton-text.inline': {
              fontFamily: fontFamily.primary,
              fontSize: 'inherit',
              padding: `0 8px`,
              lineHeight: 'normal',
              verticalAlign: 'baseline',
              '&.line-start': {
                paddingLeft: 0,
              },
              '.MuiButton-endIcon': {
                marginRight: 0,
                svg: {
                  color: 'inherit',
                },
              },
            },
          },
        },
      },
      MuiTypography: {
        variants: [
          {
            props: { variant: 'sectionTitle' },
            style: {
              color: chosenPalette.primary?.main,
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
};
