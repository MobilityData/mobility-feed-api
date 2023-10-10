import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import { type RootState } from './store';
import { type AppError, type EmailLogin } from '../types';
import { type NavigateFunction } from 'react-router-dom';

interface User {
  fullname: string | undefined;
  email: string | undefined;
  organization: string | undefined;
}

interface UserProfileState {
  status: 'unauthenticated' | 'login_in' | 'authenticated' | 'login_out';
  error: AppError | undefined;
  user: User | undefined;
}

// type  = ProfileState & User;

const initialState: UserProfileState = {
  status: 'unauthenticated',
  user: undefined,
  error: undefined,
};

// The function below is called a thunk and allows us to perform async logic. It
// can be dispatched like a regular action: `dispatch(incrementAsync(10))`. This
// will call the thunk with the `dispatch` function as the first argument. Async
// code can then be executed and other actions can be dispatched

// export const incrementAsync = createAsyncThunk<
//   number,
//   number,
//   { state: { counter: CounterState } }
// >('counter/fetchCount', async (amount: number, { getState }) => {
//   const { value } = getState().counter;
//   const response = await fetchCount(value, amount);
//   return response.data;
// });

export const userProfileSlice = createSlice({
  name: 'userProfile',
  initialState,
  reducers: {
    login: (state, action: PayloadAction<EmailLogin>) => {
      state.status = 'login_in';
    },
    loginSuccess: (state, action: PayloadAction<User>) => {
      state.status = 'authenticated';
    },
    loginFail: (state, action: PayloadAction<AppError>) => {
      state = { ...state, error: action.payload, status: 'unauthenticated' };
    },
    logout: (
      state,
      action: PayloadAction<{
        redirectScreen: string;
        navigateTo: NavigateFunction;
      }>,
    ) => {
      state.status = 'login_out';
    },
    logoutSucess: (state) => {
      state.status = 'unauthenticated';
    },
  },
});

export const { login, loginSuccess, loginFail, logout } =
  userProfileSlice.actions;

// The function below is called a selector and allows us to select a value from
// the state. Selectors can also be defined inline where they're used instead of
// in the slice file. For example: `useSelector((state: RootState) => state.counter.value)`
export const selectUserProfile = (state: RootState): User | undefined =>
  state.userProfile.user;

export const selectIsAuthenticated = (state: RootState): boolean =>
  state.userProfile.status === 'authenticated';

export default userProfileSlice.reducer;
