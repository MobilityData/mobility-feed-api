import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
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
      secondary: '#95a4f4',
      disabled: 'rgba(0,0,0,0.3)',
    },
  },
  typography: {
    fontFamily: '"Muli"',
  },
});
