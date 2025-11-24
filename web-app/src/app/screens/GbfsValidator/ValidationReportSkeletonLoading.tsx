import {
  Box,
  ListSubheader,
  ListItem,
  ListItemButton,
  ListItemIcon,
  Skeleton,
  Card,
  List,
  useTheme,
} from '@mui/material';
import { type ReactElement } from 'react';
import {
  ValidationReportTableStyles,
  ContentTitle,
} from './ValidationReport.styles';

export function ValidationReportSkeletonLoading(): ReactElement {
  const theme = useTheme();
  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'nowrap',
          gap: 2,
          maxWidth: 'lg',
          m: 'auto',
        }}
      >
        <Box id='table-content' sx={ValidationReportTableStyles}>
          <List
            aria-labelledby='nested-list-subheader'
            subheader={<ListSubheader>File Summary</ListSubheader>}
          >
            {[...Array(9)].map((_, i) => (
              <ListItem key={i} disablePadding>
                <ListItemButton>
                  <ListItemIcon>
                    <Skeleton variant='circular' width={24} height={24} />
                  </ListItemIcon>
                  <Skeleton variant='text' width={140} />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Box>
        <Box
          sx={{
            height: '100%',
            width: '100%',
            borderRadius: '5px',
            backgroundColor: theme.palette.background.paper,
            p: 0,
          }}
        >
          <ContentTitle>Validation Results</ContentTitle>
          {[...Array(9)].map((_, i) => (
            <Card key={i} sx={{ m: 2, p: 2 }}>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  pb: 1,
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Skeleton variant='circular' width={32} height={32} />
                  <Skeleton variant='text' width={110} />
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Skeleton variant='text' width={80} />
                  <Skeleton variant='circular' width={20} height={20} />
                </Box>
              </Box>
              <Box>
                <Skeleton variant='rectangular' height={24} width='60%' />
              </Box>
            </Card>
          ))}
        </Box>
      </Box>
    </Box>
  );
}
