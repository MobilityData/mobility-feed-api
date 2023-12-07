import {getAuth} from "firebase-admin/auth";

/**
 * Sets the password policy for the Firebase project.
 */
export const setPasswordPolicyConfig = async () => {
  try {
    await getAuth().projectConfigManager().updateProjectConfig({
      passwordPolicyConfig: {
        enforcementState: "ENFORCE",
        constraints: {
          requireUppercase: true,
          requireLowercase: true,
          requireNonAlphanumeric: true,
          requireNumeric: true,
          minLength: 12,
        },
      },
    });
    console.log("Password policy updated successfully");
  } catch (error) {
    console.log("Error updating password policy: " + error);
  }
};
