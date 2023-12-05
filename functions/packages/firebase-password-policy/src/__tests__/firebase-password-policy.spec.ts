import {setPasswordPolicyConfig} from "../impl/firebase-password-policy-impl";
import {getAuth} from "firebase-admin/auth";

jest.mock("firebase-admin/auth", () => ({
  getAuth: jest.fn(),
}));

describe("setPasswordPolicyConfig", () => {
  let mockUpdateProjectConfig: jest.Mock;

  beforeEach(() => {
    mockUpdateProjectConfig = jest.fn();
    (getAuth as jest.Mock).mockReturnValue({
      projectConfigManager: () => ({
        updateProjectConfig: mockUpdateProjectConfig,
      }),
    });

    // Mock console.log to verify its calls
    global.console = {log: jest.fn()} as unknown as Console;
  });

  it("should log success message when updating password policy successfully",
    async () => {
      mockUpdateProjectConfig.mockResolvedValueOnce({});

      await setPasswordPolicyConfig();

      expect(console.log)
        .toHaveBeenCalledWith("Password policy updated successfully");
    });

  it("should log error message when there is an error updating password policy",
    async () => {
      const mockError = new Error("Update failed");
      mockUpdateProjectConfig.mockRejectedValueOnce(mockError);

      await setPasswordPolicyConfig();

      expect(console.log)
        .toHaveBeenCalledWith("Error updating password policy: " + mockError);
    });
});
