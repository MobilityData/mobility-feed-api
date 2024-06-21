import { initializeApp } from 'firebase-admin/app';
import { onRequest } from 'firebase-functions/v2/https';
import { GoogleSpreadsheet } from 'google-spreadsheet';
import {JWT} from "google-auth-library";

const SCOPES = [
  'https://www.googleapis.com/auth/spreadsheets',
  'https://www.googleapis.com/auth/drive.file',
];

initializeApp();

// Replace with your spreadsheet ID
const spreadsheetId = '1fKrZqpRl7fRbSn1-0Ewx7fNmbO2G_GpLpVpuvdw3OHU';

export const writeToSheet = onRequest(
  {
    cors: '*',
    region: 'northamerica-northeast1',
  },
  async (req, res) => {
    try {
      const jwt = new JWT({
        email: "",
        key: "TODO: replace with private key",
        scopes: SCOPES,
      });

      const doc = new GoogleSpreadsheet(spreadsheetId, jwt);

      // Create a new sheet (tab)
      const newSheetTitle = 'NewSheetTitle';
      const newSheet = await doc.addSheet({ title: newSheetTitle, headerValues: ['Name', 'Age', 'City'] });

      // Write data to the new sheet
      const rows = [
        { Name: 'John Doe', Age: '30', City: 'New York' },
        { Name: 'Jane Smith', Age: '25', City: 'Los Angeles' },
      ];

      await newSheet.addRows(rows);

      res.status(200).send('Data written to the new sheet successfully!');
    } catch (error) {
      console.error('Error writing to sheet:', error);
      res.status(500).send('An error occurred while writing to the sheet.');
    }
  }
);
