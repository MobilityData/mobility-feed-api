import { Navigate, Outlet } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { selectIsAuthenticated } from '../store/selectors';
import { useEffect } from 'react';
import { app } from '../../firebase';

/**
 * This component is used to protect routes that require authentication.
 */
export const ProtectedRoute = (): JSX.Element => {
  const isAuthenticated = useSelector(selectIsAuthenticated);
  // Minimum fix for #155
  useEffect(() => {
    app.auth();
  });
  if (!isAuthenticated) {
    return <Navigate to='/' />;
  }
  return <Outlet />;
};
