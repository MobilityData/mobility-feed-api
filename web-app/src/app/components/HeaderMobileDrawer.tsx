import { OpenInNew } from '@mui/icons-material';
import {
  Box,
  Typography,
  Divider,
  List,
  Button,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  useTheme,
} from '@mui/material';
import { useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import {
  ACCOUNT_TARGET,
  gbfsMetricsNavItems,
  gtfsMetricsNavItems,
  SIGN_IN_TARGET,
} from '../constants/Navigation';
import type NavigationItem from '../interface/Navigation';
import { selectIsAuthenticated } from '../store/profile-selectors';
import { fontFamily } from '../Theme';
import { mobileNavElementStyle } from './Header.style';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useRemoteConfig } from '../context/RemoteConfigProvider';
import { useTranslation } from 'react-i18next';

const websiteTile = 'Mobility Database';

interface DrawerContentProps {
  onLogoutClick: React.MouseEventHandler;
  navigationItems: NavigationItem[];
  metricsOptionsEnabled: boolean;
}

export default function DrawerContent({
  onLogoutClick,
  navigationItems,
  metricsOptionsEnabled,
}: DrawerContentProps): JSX.Element {
  const isAuthenticated = useSelector(selectIsAuthenticated);
  const navigateTo = useNavigate();
  const { config } = useRemoteConfig();
  const { t } = useTranslation('common');
  const theme = useTheme();

  return (
    <Box>
      <Box
        sx={{ display: 'flex', alignItems: 'center' }}
        onClick={() => {
          navigateTo('/');
        }}
      >
        <picture style={{ display: 'flex' }}>
          <source
            media='(min-width: 50px)'
            srcSet='/assets/MOBILTYDATA_logo_purple_M.webp'
            width='50'
            height='50'
          />
          <source
            src='/assets/MOBILTYDATA_logo_purple_M.png'
            type='image/png'
          />
          <img
            alt='MobilityData logo'
            src='/assets/MOBILTYDATA_logo_purple_M.png'
          />
        </picture>
        <Typography
          component={'h2'}
          variant='h6'
          sx={{
            my: 2,
            cursor: 'pointer',
            color: theme.palette.primary.main,
            fontWeight: 700,
          }}
          data-testid='websiteTile'
        >
          {websiteTile}
        </Typography>
      </Box>
      <Divider />
      <List>
        {navigationItems.map((item) => (
          <Button
            variant='text'
            sx={mobileNavElementStyle}
            key={item.title}
            href={item.external === true ? item.target : '/' + item.target}
            target={item.external === true ? '_blank' : '_self'}
            rel={item.external === true ? 'noopener noreferrer' : ''}
            endIcon={item.external === true ? <OpenInNew /> : null}
            // className={activeTab.includes('/' + item.target) ? 'active' : ''}
          >
            {item.title}
          </Button>
        ))}

        <Divider sx={{ mt: 2 }} />
        {config.gbfsValidator && (
          <Accordion disableGutters={true} sx={{ boxShadow: 'none' }}>
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls='validators-content'
              id='validators-content'
            >
              <Typography
                variant={'subtitle1'}
                sx={{ fontFamily: fontFamily.secondary }}
              >
                {t('validators')}
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Button
                variant='text'
                sx={mobileNavElementStyle}
                href={'gbfs-validator'}
              >
                {t('gbfsValidator')}
              </Button>
              <Button variant='text' sx={mobileNavElementStyle} disabled={true}>
                {t('gtfsValidator')}
              </Button>
            </AccordionDetails>
          </Accordion>
        )}
        {metricsOptionsEnabled && (
          <>
            <Accordion disableGutters={true} sx={{ boxShadow: 'none' }}>
              <AccordionSummary
                expandIcon={<ExpandMoreIcon />}
                aria-controls='gtfs-metrics-content'
                id='gtfs-metrics-content'
              >
                <Typography
                  variant={'subtitle1'}
                  sx={{ fontFamily: fontFamily.secondary }}
                >
                  GTFS Metrics
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                {gtfsMetricsNavItems.map((item) => (
                  <Button
                    variant='text'
                    sx={mobileNavElementStyle}
                    key={item.title}
                    href={item.target}
                  >
                    {item.title}
                  </Button>
                ))}
              </AccordionDetails>
            </Accordion>
            <Accordion disableGutters={true} sx={{ boxShadow: 'none' }}>
              <AccordionSummary
                expandIcon={<ExpandMoreIcon />}
                aria-controls='gbfs-metrics-content'
                id='gbfs-metrics-content'
              >
                <Typography
                  variant={'subtitle1'}
                  sx={{ fontFamily: fontFamily.secondary }}
                >
                  GBFS Metrics
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                {gbfsMetricsNavItems.map((item) => (
                  <Button
                    variant='text'
                    sx={mobileNavElementStyle}
                    key={item.title}
                    href={item.target}
                  >
                    {item.title}
                  </Button>
                ))}
              </AccordionDetails>
            </Accordion>
          </>
        )}

        {isAuthenticated ? (
          <Accordion disableGutters={true} sx={{ boxShadow: 'none' }}>
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls='account-content'
              id='account-header'
            >
              <Typography
                variant={'subtitle1'}
                sx={{ fontFamily: fontFamily.secondary }}
              >
                Account
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Button
                variant='text'
                sx={mobileNavElementStyle}
                href={ACCOUNT_TARGET}
              >
                Account Details
              </Button>
              <Button
                variant='text'
                sx={mobileNavElementStyle}
                onClick={onLogoutClick}
              >
                Sign Out
              </Button>
            </AccordionDetails>
          </Accordion>
        ) : (
          <Button variant='contained' sx={{ ml: 2 }} href={SIGN_IN_TARGET}>
            Login
          </Button>
        )}
      </List>
    </Box>
  );
}
