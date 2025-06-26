import { Box, styled} from "@mui/material";

interface StyledMapControlPanelProps {
  showMapControlMobile: boolean;
}

export const StyledMapControlPanel = styled(Box, {
  shouldForwardProp: (prop) => prop !== 'showMapControlMobile',
})<StyledMapControlPanelProps>(({ theme, showMapControlMobile }) => ({
  padding: theme.spacing(2),
  paddingTop: '100px', // to account for the fixed header on mobile
  flexDirection: 'column',
  flexWrap: 'nowrap',
  backgroundColor: theme.palette.background.default,
  zIndex: 10000,
  display: showMapControlMobile ? 'flex' : 'none',
  width: '100%',
  position: 'fixed',
  top: 0,
  height: '100%',
  overflowY: 'auto',

  [theme.breakpoints.up('md')]: {
    display: 'flex',
    width: '300px',
    position: 'relative',
    top: 'unset',
    paddingTop: 0
  },
}));

export const StyledChipFilterContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(1),
  padding: theme.spacing(1),
  minHeight: '50px',
  flexWrap: 'nowrap',
  overflowX: 'auto',

  [theme.breakpoints.up('md')]: {
    flexWrap: 'wrap',
    overflowX: 'hidden',
  },
}));

