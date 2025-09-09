import * as React from 'react';
import {
  Box,
  Paper,
  TableCell,
  TableRow,
  Tooltip,
  TableBody,
  Table,
  TableContainer,
  Typography,
} from '@mui/material';
import { type Theme } from '@mui/material/styles';

interface PopupTableProps {
  properties: Record<string, string | number>;
  theme: Theme;
}

const fieldDescriptions: Record<string, { description?: string }> = {
  stops_in_area: {
    description:
      'This is the number of stops in stops.txt that are located within this geographic area.',
  },
  stops_in_area_coverage: {
    description:
      'Percentage of stops from stops.txt that are located within this geographic area.',
  },
};

export const PopupTable: React.FC<PopupTableProps> = ({
  properties,
  theme,
}) => {
  const displayName = properties?.display_name ?? 'Details';

  // Create rows for each property (exclude 'color' and 'display_name')
  const rows = Object.keys(properties)
    .filter((key) => key !== 'color' && key !== 'display_name')
    .map((key) => {
      const fieldInfo = fieldDescriptions[key] ?? {};
      const formattedKey = key
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());

      return (
        <TableRow key={key}>
          <TableCell sx={{ color: theme.palette.text.primary }}>
            <b>{formattedKey} </b>
            {fieldInfo.description != null && (
              <Tooltip title={fieldInfo.description} arrow>
                <span style={{ cursor: 'help' }}>ℹ️</span>
              </Tooltip>
            )}
          </TableCell>
          <TableCell sx={{ color: theme.palette.text.primary }}>
            {properties[key]}
          </TableCell>
        </TableRow>
      );
    });

  return (
    <Box
      sx={{
        background: theme.palette.background.paper,
        color: theme.palette.text.primary,
        maxWidth: '300px',
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: theme.shape.borderRadius,
        padding: theme.spacing(1),
      }}
    >
      <Typography
        variant={'h6'}
        sx={{ mb: 1, fontSize: '1.0rem', fontWeight: 700 }}
      >
        {displayName}
      </Typography>
      <TableContainer
        component={Paper}
        elevation={2}
        sx={{
          background: theme.palette.background.default,
          color: theme.palette.text.primary,
        }}
      >
        <Table size='small'>
          <TableBody>{rows}</TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};
