import React from 'react';
import { Routes, Route } from 'react-router-dom';
import SignIn from '../screens/SignIn';
import SignUp from '../screens/SignUp';
import Account from '../screens/Account';
import ContactInformation from '../screens/ContactInformation';
import { ProtectedRoute } from './ProtectedRoute';
import CompleteRegistration from '../screens/CompleteRegistration';
import ChangePassword from '../screens/ChangePassword';
import Home from '../screens/Home';
import ForgotPassword from '../screens/ForgotPassword';
import FAQ from '../screens/FAQ';
import About from '../screens/About';
import Contribute from '../screens/Contribute';
import PostRegistration from '../screens/PostRegistration';

export const AppRouter: React.FC = () => {
  return (
    <Routes>
      <Route path='/' element={<Home />} />
      <Route path='sign-in' element={<SignIn />} />
      <Route path='sign-up' element={<SignUp />} />
      <Route element={<ProtectedRoute targetStatus='authenticated' />}>
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
      <Route element={<ProtectedRoute targetStatus='unverified' />}>
        <Route path='verify-email' element={<PostRegistration />} />
      </Route>
      <Route path='forgot-password' element={<ForgotPassword />} />
      <Route path='faq' element={<FAQ />} />
      <Route path='about' element={<About />} />
      <Route path='contribute' element={<Contribute />} />
    </Routes>
  );
};

export default AppRouter;
