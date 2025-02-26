import { IconButton } from '@mui/material';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import { useTheme } from '../context/ThemeProvider';

const ThemeToggle = (): JSX.Element => {
  const { toggleTheme } = useTheme();

  return (
    <IconButton onClick={toggleTheme} color='inherit'>
      {localStorage.getItem('theme') === 'dark' ? (
        <Brightness7Icon />
      ) : (
        <Brightness4Icon />
      )}
    </IconButton>
  );
};

export default ThemeToggle;
