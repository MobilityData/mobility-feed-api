import { createBrowserRouter } from "react-router-dom"
import SignInScreen from "./SignInScreen";
import RegisterScreen from "./RegisterScreen";

const appRouter = createBrowserRouter([
    {
        path: "signin",
        element: <SignInScreen />,
    },
    {
        path: "register",
        element: <RegisterScreen />
    }
]);

export default appRouter;