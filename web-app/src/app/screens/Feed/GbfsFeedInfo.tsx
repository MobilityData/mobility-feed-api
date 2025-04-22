import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Box,
  Button,
  Chip,
  Grid,
  type SxProps,
  Typography,
  Snackbar,
  styled,
  IconButton,
  Tooltip,
  useTheme,
  Link,
} from '@mui/material';
import { ContentCopy, ContentCopyOutlined } from '@mui/icons-material';
import {
  GBFSFeedType,
  type GTFSFeedType,
  type GTFSRTFeedType,
} from '../../services/feeds/utils';
import { type components } from '../../services/feeds/types';
import { useTranslation } from 'react-i18next';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { getDataFeatureUrl } from '../../utils/consts';
import PublicIcon from '@mui/icons-material/Public';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import LinkIcon from '@mui/icons-material/Link';
import DatasetIcon from '@mui/icons-material/Dataset';
import LayersIcon from '@mui/icons-material/Layers';
import EmailIcon from '@mui/icons-material/Email';
import LockIcon from '@mui/icons-material/Lock';
import DateRangeIcon from '@mui/icons-material/DateRange';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { FeedStatusIndicator } from '../../components/FeedStatus';
import Locations from '../../components/Locations';
import { formatServiceDateRange } from './Feed.functions';
import SettingsIcon from '@mui/icons-material/Settings';
import BikeScooterIcon from '@mui/icons-material/BikeScooter';

export interface GbfsFeedInfoProps {
  feed: GBFSFeedType
}

// TODO: Refactor this
const boxElementStyle: SxProps = {
  width: '100%',
  mt: 2,
  mb: 1,
};

const boxElementStyleTransitProvider: SxProps = {
  width: '100%',
  mt: 2,
  borderBottom: 'none',
};

const boxElementStyleProducerURL: SxProps = {
  width: '100%',
  mb: 1,
};

const StyledTitleContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  gap: theme.spacing(1),
  marginBottom: '4px',
  marginTop: theme.spacing(3),
  alignItems: 'center',
}));

const ResponsiveListItem = styled('li')(({ theme }) => ({
  width: '100%',
  margin: '5px 0',
  fontWeight: 'normal',
  fontSize: '16px',
  [theme.breakpoints.up('lg')]: {
    width: 'calc(50% - 15px)',
  },
}));

// TODO: Refactor this

export default function GbfsFeedInfo({
  feed,
}: GbfsFeedInfoProps): React.ReactElement {
  const { t } = useTranslation('feeds');
  const theme = useTheme();

  const hasAuthenticationInfo =
  feed?.source_info?.authentication_info_url != undefined &&
  feed?.source_info.authentication_info_url.trim() !== '';

  return (
    <ContentBox
      title={'Feed Info'}
      outlineColor={theme.palette.primary.dark}
      padding={2}
    >
      <Box sx={boxElementStyle}>
        <StyledTitleContainer>
          <PublicIcon></PublicIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            {t('locations')}
          </Typography>
        </StyledTitleContainer>
        <Box data-testid='location'>
          {feed?.locations != null && <Locations locations={feed?.locations} />}
        </Box>
      </Box>

      <Box sx={boxElementStyle}>
        <StyledTitleContainer>
          <LinkIcon></LinkIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            Producer
          </Typography>
        </StyledTitleContainer>
        <Link href='www.uber.com' variant='body1'>
          {feed?.provider}
        </Link>
      </Box>

      <Box sx={boxElementStyle}>
        <StyledTitleContainer>
          <SettingsIcon></SettingsIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            System ID
          </Typography>
        </StyledTitleContainer>
        <Typography variant='body1'>{feed?.system_id}</Typography>
      </Box>

      <Box sx={boxElementStyle}>
        <StyledTitleContainer>
          <DatasetIcon></DatasetIcon>
          <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
            Data Format
          </Typography>
        </StyledTitleContainer>
        <Typography variant='body1'>GBFS</Typography>
      </Box>

      {/* TODO: auth elements can be refactored to a separate component */}
      {feed?.source_info?.authentication_type !== 0 && (
        <Box sx={boxElementStyle}>
          <StyledTitleContainer>
            <LockIcon></LockIcon>
            <Typography variant='subtitle1' sx={{ fontWeight: 'bold' }}>
              {t('authenticationType')}
            </Typography>
            <Typography data-testid='data-type'>
              {feed?.source_info?.authentication_type === 1 &&
                t('common:apiKey')}
              {feed?.source_info?.authentication_type === 2 &&
                t('common:httpHeader')}
            </Typography>
          </StyledTitleContainer>
        </Box>
      )}

      {hasAuthenticationInfo &&
        feed?.source_info?.authentication_info_url != undefined && (
          <Button
            disableElevation
            variant='outlined'
            href={feed?.source_info?.authentication_info_url}
            target='_blank'
            rel='noreferrer'
            sx={{ marginRight: 2 }}
            endIcon={<OpenInNewIcon />}
          >
            {t('registerToDownloadFeed')}
          </Button>
        )}
     
    </ContentBox>
  );
}
