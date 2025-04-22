import * as React from 'react';
import { ContentBox } from '../../components/ContentBox';
import {
  Box,
  Button,
  Chip,
  IconButton,
  Link,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import {
  DownloadOutlined,
  ReportOutlined,
  LaunchOutlined,
  CheckCircle,
} from '@mui/icons-material';
import { type paths } from '../../services/feeds/types';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import SummarizeIcon from '@mui/icons-material/Summarize';
import CodeIcon from '@mui/icons-material/Code';
import DateRangeIcon from '@mui/icons-material/DateRange';
import { WEB_VALIDATOR_LINK } from '../../constants/Navigation';
import { formatServiceDateRange } from './Feed.functions';
import { useTranslation } from 'react-i18next';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { GBFSFeedType } from '../../services/feeds/utils';
import { displayFormattedDate } from '../../utils/date';

export interface GbfsVersionsProps {
  feed: GBFSFeedType;
}

const sampleData = [
  {
    version: 'v3.0',
    autoDiscovery:
      'https://buenosaires.publicbikesystem.net/customer/gbfs/v3/gbfs.json	',
    validationReportTimestamp: '2023-10-01T12:00:00Z',
    validationErrors: 0,
    features: [
      'Manifest',
      'Geofencing',
      'Pricing Plans',
      'Bike Availability',
      'Station',
      'Vehicle Types',
      'Station',
      'Vehicle Types',
    ],
  },
  {
    version: 'v2.0',
    autoDiscovery:
      'https://buenosaires.publicbikesystem.net/customer/gbfs/v2/gbfs.json	',
    validationReportTimestamp: '2023-10-01T12:00:00Z',
    validationErrors: 0,
    features: [
      'Manifest',
      'Geofencing',
      'Pricing Plans',
      'Bike Availability',
      'Station',
      'Vehicle Types',
    ],
  },
  {
    version: 'v1.0',
    autoDiscovery:
      'https://buenosaires.publicbikesystem.net/customer/gbfs/v1/gbfs.json	',
    validationReportTimestamp: '2023-10-01T12:00:00Z',
    validationErrors: 3,
    features: ['Manifest', 'Station', 'Vehicle Types'],
  },
];




export default function GbfsVersions({
  feed,
}: GbfsVersionsProps): React.ReactElement {
  const theme = useTheme();
  const { t } = useTranslation('feeds');

  return (
    <>
      <Typography
        sx={{ fontSize: { xs: 18, sm: 24 }, fontWeight: 'bold', mb: 1 }}
      >
        Versions
      </Typography>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          flexWrap: 'wrap',
          gap: 3,
          justifyContent: 'flex-end',
        }}
      >
        {feed?.versions?.map((item, index) => (
          <ContentBox
            key={index}
            title={``}
            outlineColor={theme.palette.secondary.main}
            padding={2}
            sx={{
              my: 0,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
            width={{ xs: '100%'}}
          >
            <Box>
              <Box>
                <Typography
                  variant='h5'
                  sx={{
                    mb: 1,
                    fontWeight: 'bold',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  {item.version}
                  {index === 0 && (
                    <Chip
                      label='latest'
                      variant='filled'
                      color='primary'
                      sx={{ ml: 2 }}
                    />
                  )}
                  <Chip
                    icon={
                      item.latest_validation_report?.total_error === 0 ? (
                        <CheckCircleIcon />
                      ) : (
                        <ErrorIcon />
                      )
                    }
                    label={
                      item.latest_validation_report?.total_error != null && item.latest_validation_report?.total_error > 0
                        ? `${item.latest_validation_report?.total_error} errors`
                        : 'no errors'
                    }
                    variant='outlined'
                    color={item.latest_validation_report?.total_error != null && item.latest_validation_report?.total_error > 0 ? 'error' : 'success'}
                    sx={{ ml: 2 }}
                  />
                </Typography>
                <Typography
                  variant='caption'
                  component={'div'}
                  sx={{ mt: '-2px', mb: 2 }}
                >
                  Quality report updated at: {displayFormattedDate(item.latest_validation_report?.validated_at ?? '')} 
                  {/* TODO: timezone? */}
                  
                </Typography>
                <Typography variant='h6' sx={{ fontSize: '1.1rem' }}>
                  Auto-Discovery Url
                </Typography>
                <Box
                  sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}
                >
                  {/* <Link href={item.autoDiscovery}>{item.autoDiscovery}</Link> */}
                  <ContentCopyIcon></ContentCopyIcon>
                </Box>
                <Box>
                  <Typography variant='h6' sx={{ mt: 1, fontSize: '1.1rem' }}>
                    Features
                  </Typography>
                  {item.endpoints?.map((endpoint, index) => (
                    <Chip
                      key={index}
                      label={endpoint.name}
                      color='info'
                      variant='filled'
                      sx={{ margin: '4px' }}
                    />
                  ))}
                </Box>
              </Box>
              </Box>
              <Box
                sx={{
                  width: '100%',
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: 2,
                  mt: 3,
                }}
              >
                {/* <Button variant='text' color='primary' >
              View Visualization
            </Button> */}
                <Button variant='text' color='primary'>
                  Run Validation Report
                </Button>
                <Button
                  variant='contained'
                  color='primary'
                  endIcon={<OpenInNewIcon></OpenInNewIcon>}
                >
                  Open Feed Url
                </Button>
              </Box>
           
          </ContentBox>
        ))}
      </Box>
    </>
  );
}
