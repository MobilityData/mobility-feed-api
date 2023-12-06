import React from 'react';
import { Routes, Route } from 'react-router-dom';
import SignIn from '../screens/SignIn';
import SignUp from '../screens/SingUp';
import Account from '../screens/Account';
import ContactInformation from '../screens/ContactInformation';
import { ProtectedRoute } from './ProtectedRoute';
import CompleteRegistration from '../screens/CompleteRegistration';
import ChangePassword from '../screens/ChangePassword';
import ForgotPassword from '../screens/ForgotPassword';

export const AppRouter: React.FC = () => {
  return (
    <Routes>
      <Route path='/' element={<SignIn />} />
      <Route path='sign-in' element={<SignIn />} />
      <Route path='sign-up' element={<SignUp />} />
      <Route element={<ProtectedRoute />}>
        <Route
          path='complete-registration'
          element={<CompleteRegistration />}
        />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route path='account' element={<Account />} />
      </Route>
      <Route path='contact-info' element={<ContactInformation />} />
      <Route element={<ProtectedRoute />}>
        <Route path='change-password' element={<ChangePassword />} />
      </Route>
      <Route path='forgot-password' element={<ForgotPassword />} />
    </Routes>
  );
};

export default AppRouter;
