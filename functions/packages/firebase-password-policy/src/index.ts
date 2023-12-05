import {initializeApp} from "firebase-admin/app";
import * as impl from "./impl/firebase-password-policy-impl";

initializeApp();
impl.setPasswordPolicyConfig().then();
