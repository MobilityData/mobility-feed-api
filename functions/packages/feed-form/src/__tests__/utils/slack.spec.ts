import { sendSlackWebhook } from "../../impl/utils/slack";
import axios from "axios";
import * as logger from "firebase-functions/logger";

jest.mock("axios");
jest.mock("firebase-functions/logger");

describe("sendSlackWebhook", () => {
  const spreadsheetId = "sheet123";
  const githubIssueUrl = "https://github.com/issue/1";
  const oldEnv = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env = { ...oldEnv, SLACK_WEBHOOK_URL: "https://hooks.slack.com/services/abc" };
  });

  afterAll(() => {
    process.env = oldEnv;
  });

  it("sends a Slack message with correct payload", async () => {
    (axios.post as jest.Mock).mockResolvedValueOnce({});
    await sendSlackWebhook(spreadsheetId, githubIssueUrl, true);
    expect(axios.post).toHaveBeenCalledWith(
      process.env.SLACK_WEBHOOK_URL,
      expect.objectContaining({ blocks: expect.any(Array) })
    );
  });

  it("logs error if webhook URL is not set", async () => {
    process.env.SLACK_WEBHOOK_URL = "";
    await sendSlackWebhook(spreadsheetId, githubIssueUrl, false);
    expect(logger.error).toHaveBeenCalledWith("Slack webhook URL is not defined");
  });

  it("logs error if axios fails", async () => {
    (axios.post as jest.Mock).mockRejectedValueOnce(new Error("fail"));
    await sendSlackWebhook(spreadsheetId, githubIssueUrl, false);
    expect(logger.error).toHaveBeenCalled();
  });
});
