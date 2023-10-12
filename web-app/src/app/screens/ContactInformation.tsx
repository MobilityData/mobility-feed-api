import * as React from 'react';
import CssBaseline from '@mui/material/CssBaseline';
import {
  Typography,
  Container,
  TextField,
  FormControlLabel,
  Checkbox,
  Button,
  Box,
} from '@mui/material';

export default function ContactInformation(): React.ReactElement {
  const [inputValues, setValues] = React.useState({
    firstName: '',
    lastName: '',
    organizationName: '',
    receiveUpdates: false,
  });

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const { name, value } = e.target;
    setValues({
      ...inputValues,
      [name]: value,
    });
  };

  const handleCheckboxChange = (
    e: React.ChangeEvent<HTMLInputElement>,
  ): void => {
    setValues({
      ...inputValues,
      receiveUpdates: e.target.checked,
    });
  };

  return (
    <Container
      component='main'
      sx={{ mt: 12, display: 'flex', flexDirection: 'column' }}
    >
      <CssBaseline />
      <Typography
        component='h1'
        variant='h5'
        color='secondary'
        sx={{ fontWeight: 'bold', textAlign: 'left' }}
      >
        API Account Setup
      </Typography>
      <Typography
        component='h2'
        variant='h6'
        color='primary'
        sx={{ mt: 2, mb: 2, fontWeight: 'bold', textAlign: 'left' }}
      >
        Contact Information
      </Typography>

      <TextField
        variant='outlined'
        margin='normal'
        required
        id='firstName'
        label='First Name'
        name='firstName'
        autoFocus
        value={inputValues.firstName}
        onChange={handleInputChange}
        sx={{ width: '50%' }}
      />
      <TextField
        variant='outlined'
        margin='normal'
        required
        id='lastName'
        label='Last Name'
        name='lastName'
        value={inputValues.lastName}
        onChange={handleInputChange}
        sx={{ width: '50%' }}
      />
      <TextField
        variant='outlined'
        margin='normal'
        required
        id='organizationName'
        label='Organization Name'
        name='organizationName'
        value={inputValues.organizationName}
        onChange={handleInputChange}
        sx={{ width: '50%' }}
      />

      <FormControlLabel
        control={
          <Checkbox
            checked={inputValues.receiveUpdates}
            onChange={handleCheckboxChange}
            name='receiveUpdates'
            color='primary'
          />
        }
        label='I would like to receive new API release announcements via email.'
      />
      <Box sx={{ display: 'flex', justifyContent: 'left' }}>
        <Button
          type='submit'
          variant='contained'
          color='primary'
          sx={{ mt: 3, mb: 2 }}
        >
          Finish Account Setup
        </Button>
      </Box>
    </Container>
  );
}
