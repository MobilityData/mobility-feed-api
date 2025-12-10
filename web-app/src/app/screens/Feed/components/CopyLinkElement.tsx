import { type ReactElement, useState } from 'react';
import { FeedLinkElement } from '../FeedSummary.styles';
import {
  Box,
  Button,
  Chip,
  IconButton,
  Link,
  Snackbar,
  Tooltip,
  Typography,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DownloadIcon from '@mui/icons-material/Download';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import EmailIcon from '@mui/icons-material/Email';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

export interface CopyLinkElementProps {
  title?: string;
  url: string;
  linkType?: 'download' | 'external' | 'email' | 'internal';
  titleInfo?: string;
  internalClickAction?: () => void;
}

export default function CopyLinkElement({
  title,
  url,
  linkType,
  titleInfo,
  internalClickAction,
}: CopyLinkElementProps): ReactElement {
  const [snackbarOpen, setSnackbarOpen] = useState(false);

  let chipIcon: JSX.Element | undefined;
  let chipLabel: string | undefined;
  switch (linkType) {
    case 'download':
      chipIcon = <DownloadIcon />;
      chipLabel = 'Download';
      break;
    case 'external':
      chipIcon = <OpenInNewIcon />;
      chipLabel = 'External Link';
      break;
    case 'email':
      chipIcon = <EmailIcon />;
      chipLabel = 'Email';
      break;
  }
  const formattedUrl = linkType === 'email' ? `mailto:${url}` : url;

  return (
    <FeedLinkElement>
      {title != null && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {linkType === 'internal' ? (
            <Button
              variant='text'
              sx={{ pl: 0, py: 0.5 }}
              onClick={internalClickAction}
            >
              {title}
            </Button>
          ) : (
            <Button
              variant='text'
              sx={{ pl: 0, py: 0.5 }}
              component={Link}
              href={formattedUrl}
              target='_blank'
              rel='noreferrer'
            >
              {title}
            </Button>
          )}
          {titleInfo != undefined && (
            <Tooltip title={titleInfo} placement='top'>
              <InfoOutlinedIcon fontSize='inherit' />
            </Tooltip>
          )}
          {chipIcon != undefined && chipLabel != undefined && (
            <Chip
              clickable
              component={Link}
              href={formattedUrl}
              target='_blank'
              rel='noreferrer'
              size='small'
              label={chipLabel}
              icon={chipIcon}
              sx={{ color: 'text.secondary', fontWeight: 400 }}
            ></Chip>
          )}
        </Box>
      )}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography
          variant='subtitle2'
          sx={{
            fontWeight: 400,
            whiteSpace: 'nowrap',
            overflowX: 'auto',
            color: 'text.secondary',
          }}
        >
          {url}
        </Typography>
        <Tooltip title='Copy Url' placement='top'>
          <IconButton
            onClick={() => {
              setSnackbarOpen(true);
              void navigator.clipboard.writeText(url);
            }}
            sx={{ svg: { width: '0.875em', height: '0.875em' } }}
            size='small'
            aria-label='copy link'
          >
            <ContentCopyIcon />
          </IconButton>
        </Tooltip>
        <Snackbar
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
          open={snackbarOpen}
          autoHideDuration={5000}
          onClose={() => {
            setSnackbarOpen(false);
          }}
          message={'URL copied to clipboard'}
        />
      </Box>
    </FeedLinkElement>
  );
}
