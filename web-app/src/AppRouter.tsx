import { createBrowserRouter } from "react-router-dom"
import SignInScreen from "./components/SignInScreen";
import RegisterScreen from "./components/RegisterScreen";

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