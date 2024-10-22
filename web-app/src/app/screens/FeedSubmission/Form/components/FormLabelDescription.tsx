import { Typography } from '@mui/material';
import { type ReactNode } from 'react';

interface FormLabelDescriptionProps {
  children: ReactNode;
}

const FormLabelDescription: React.FC<FormLabelDescriptionProps> = ({
  children,
}) => {
  return (
    <Typography variant='caption' mb={'4px'}>
      {children}
    </Typography>
  );
};

export default FormLabelDescription;
