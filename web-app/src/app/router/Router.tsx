import React from 'react';
import { Routes, Route } from 'react-router-dom';
import SignIn from '../sign-in-page/SignIn';
import SignUp from '../sign-up-page/SingUp';
import Account from '../account-page/Account';
import ContactInformation from '../contact-information-page/ContactInformation';

export const AppRouter: React.FC = () => {
  return (
    <Routes>
      <Route path='/' element={<SignIn />} />
      <Route path='sign-in' element={<SignIn />} />
      <Route path='sign-up' element={<SignUp />} />
      <Route path='account' element={<Account />} />
      <Route path='contact-info' element={<ContactInformation />} />
    </Routes>
  );
};

export default AppRouter;
