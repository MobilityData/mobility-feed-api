import axios from "axios";
import * as logger from "firebase-functions/logger";

/**
 * Sends a Slack webhook message to the configured Slack webhook URL
 * @param {string} spreadsheetId The ID of the Google Sheet
 * @param {string} githubIssueUrl The URL of the created GitHub issue
 * @param {boolean} isOfficialSource Whether the feed is an official source
 */
export async function sendSlackWebhook(
  spreadsheetId: string,
  githubIssueUrl: string,
  isOfficialSource: boolean
) {
  const slackWebhookUrl = process.env.SLACK_WEBHOOK_URL;
  const sheetUrl = `https://docs.google.com/spreadsheets/d/${spreadsheetId}/edit`;
  if (slackWebhookUrl !== undefined && slackWebhookUrl !== "") {
    let headerText = "New Feed Added";
    if (isOfficialSource) {
      headerText += " 🔹 Official Source";
    }
    const linksElement = [
      {
        type: "emoji",
        name: "google_drive",
      },
      {
        type: "link",
        url: sheetUrl,
        text: " View Feed ",
        style: {
          bold: true,
        },
      },
    ];
    if (githubIssueUrl !== "") {
      linksElement.push(
        {
          type: "emoji",
          name: "github-logo",
        },
        {
          type: "link",
          url: githubIssueUrl,
          text: " View Issue ",
          style: {
            bold: true,
          },
        }
      );
    }
    const slackMessage = {
      blocks: [
        {
          type: "header",
          text: {
            type: "plain_text",
            text: headerText,
            emoji: true,
          },
        },
        {
          type: "rich_text",
          elements: [
            {
              type: "rich_text_section",
              elements: [
                {
                  type: "emoji",
                  name: "inbox_tray",
                },
                {
                  type: "text",
                  text: "  A new entry was received in the OpenMobilityData source updates Google Sheet",
                },
              ],
            },
          ],
        },
        {
          type: "rich_text",
          elements: [
            {
              type: "rich_text_section",
              elements: linksElement,
            },
          ],
        },
      ],
    };
    await axios.post(slackWebhookUrl, slackMessage).catch((error) => {
      logger.error("Error sending Slack webhook:", error);
    });
  } else {
    logger.error("Slack webhook URL is not defined");
  }
}