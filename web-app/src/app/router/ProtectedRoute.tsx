import { Navigate, Outlet } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { selectIsAuthenticated } from '../store/selectors';
import { useEffect } from 'react';
import { app } from '../../firebase';
import { onAuthStateChanged } from 'firebase/auth';
import { User } from 'firebase/auth';

/**
 * This component is used to protect routes that require authentication.
 */
export const ProtectedRoute = (): JSX.Element => {
  const isAuthenticated = useSelector(selectIsAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to='/' />;
  }
  return <Outlet />;
};
