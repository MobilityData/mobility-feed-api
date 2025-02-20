import * as React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  Paper,
  Tooltip,
} from '@mui/material';

interface PopupTableProps {
  properties: Record<string, any>;
}

// Map for custom field labels and descriptions
const fieldDescriptions: Record<string, { description?: string }> = {
  stops_in_area: {
    description:
      'This is the number of stops in stops.txt that are in this geographic area.',
  },
  stops_in_area_coverage: {
    description:
      'Percentage of stops from stops.txt that are located within this geographic area.',
  },
};

export const PopupTable: React.FC<PopupTableProps> = ({ properties }) => {
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
          <TableCell>
            {formattedKey}{' '}
            {fieldInfo.description != null && (
              <Tooltip title={fieldInfo.description} arrow>
                <span style={{ cursor: 'help' }}>ℹ️</span>
              </Tooltip>
            )}
          </TableCell>
          <TableCell>{properties[key]} </TableCell>
        </TableRow>
      );
    });

  return (
    <div style={{ maxWidth: '300px' }}>
      <h3 style={{ margin: '0 0 8px 0' }}>{displayName}</h3>
      <TableContainer component={Paper} elevation={2}>
        <Table size='small'>
          <TableBody>{rows}</TableBody>
        </Table>
      </TableContainer>
    </div>
  );
};
