const https = require("https");
const { URL } = require("url");

const STATUS_STYLE = {
  SUCCEED: { color: 0x2ecc71, emoji: "✅", label: "Build succeeded" },
  FAILED: { color: 0xe74c3c, emoji: "❌", label: "Build failed" },
  STARTED: { color: 0x3498db, emoji: "🚀", label: "Build started" },
  PENDING: { color: 0xf1c40f, emoji: "⏳", label: "Build pending" },
  CANCELLED: { color: 0x95a5a6, emoji: "🛑", label: "Build cancelled" },
};

exports.handler = async (event) => {
  const webhookUrl = process.env.DISCORD_WEBHOOK_URL;
  if (!webhookUrl) {
    throw new Error("DISCORD_WEBHOOK_URL environment variable is not set");
  }

  const detail = event.detail || {};
  const { appId, branchName, jobId, jobStatus } = detail;
  const style = STATUS_STYLE[jobStatus] || {
    color: 0x7f8c8d,
    emoji: "ℹ️",
    label: jobStatus || "Build status changed",
  };

  const consoleUrl =
    appId && branchName
      ? `https://console.aws.amazon.com/amplify/home?#/${appId}/${branchName}/${jobId}`
      : undefined;

  const embed = {
    title: `${style.emoji} ${style.label}`,
    color: style.color,
    fields: [
      { name: "App", value: appId || "unknown", inline: true },
      { name: "Branch", value: branchName || "unknown", inline: true },
      { name: "Job", value: jobId || "unknown", inline: true },
    ],
    timestamp: new Date().toISOString(),
    ...(consoleUrl ? { url: consoleUrl } : {}),
  };

  await postToDiscord(webhookUrl, { embeds: [embed] });

  return { statusCode: 200 };
};

function postToDiscord(webhookUrl, payload) {
  return new Promise((resolve, reject) => {
    const url = new URL(webhookUrl);
    const body = JSON.stringify(payload);

    const req = https.request(
      {
        hostname: url.hostname,
        path: `${url.pathname}${url.search}`,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(data);
          } else {
            reject(new Error(`Discord webhook returned ${res.statusCode}: ${data}`));
          }
        });
      }
    );

    req.on("error", reject);
    req.write(body);
    req.end();
  });
}
