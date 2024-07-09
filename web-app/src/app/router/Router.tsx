import React, { useEffect } from 'react';
import { Routes, Route, useNavigate } from 'react-router-dom';
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
import TermsAndConditions from '../screens/TermsAndConditions';
import PrivacyPolicy from '../screens/PrivacyPolicy';
import Feed from '../screens/Feed';
import Feeds from '../screens/Feeds';
import { SIGN_OUT_TARGET } from '../constants/Navigation';
import {
  LOGIN_CHANNEL,
  LOGOUT_CHANNEL,
  createDispatchChannel,
} from '../services/channel-service';
import { useAppDispatch } from '../hooks';
import { logout } from '../store/profile-reducer';

export const AppRouter: React.FC = () => {
  const navigateTo = useNavigate();
  const dispatch = useAppDispatch();
  const logoutUser = (): void => {
    dispatch(
      logout({ redirectScreen: SIGN_OUT_TARGET, navigateTo, propagate: false }),
    );
  };

  const loginUser = (): void => {
    // Refresh the page to ensure the user is authenticated
    window.location.reload();
  };

  useEffect(() => {
    createDispatchChannel(LOGOUT_CHANNEL, logoutUser);
    createDispatchChannel(LOGIN_CHANNEL, loginUser);
  }, [dispatch]);

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
      <Route path='feeds' element={<Feeds />} />
      <Route path='feeds/:feedId' element={<Feed />} />
      <Route path='contribute' element={<Contribute />} />
      <Route path='privacy-policy' element={<PrivacyPolicy />} />
      <Route path='terms-and-conditions' element={<TermsAndConditions />} />
    </Routes>
  );
};

export default AppRouter;
