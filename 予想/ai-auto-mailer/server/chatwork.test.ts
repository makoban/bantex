import { describe, it, expect } from "vitest";
import { sendChatworkNotification } from "./chatworkService";

describe("Chatwork API Integration", () => {
  it("should send notification to Chatwork room", async () => {
    const apiToken = process.env.CHATWORK_API_TOKEN;
    const roomId = "419007473"; // Test room ID

    if (!apiToken) {
      console.log("CHATWORK_API_TOKEN not set, skipping test");
      expect(true).toBe(true);
      return;
    }

    const testEmails = [
      {
        sender: "test@example.com",
        subject: "Test Email",
        summary: "This is a test email summary",
        importance: "high" as const,
      },
    ];

    const result = await sendChatworkNotification(apiToken, roomId, testEmails);
    expect(result).toBe(true);
  });

  it("should handle missing parameters gracefully", async () => {
    const result = await sendChatworkNotification("", "", []);
    expect(result).toBe(false);
  });
});
