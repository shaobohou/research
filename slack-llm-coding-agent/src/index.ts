/**
 * Entry point: Slack bot using Bolt (Socket Mode) that delegates
 * coding requests to the pi-ai powered agent loop.
 */

import { App } from "@slack/bolt";
import { loadConfig, type Config } from "./config.js";
import { runAgent } from "./agent.js";

// Track channels where the agent is currently working so we don't overlap.
const busyChannels = new Set<string>();

async function main() {
  const config = loadConfig();
  console.log(`Workspace directory: ${config.workspaceDir}`);
  console.log(`LLM: ${config.llmProvider} / ${config.llmModel}`);

  const app = new App({
    token: config.slackBotToken,
    appToken: config.slackAppToken,
    socketMode: true,
  });

  // --- Handle @mentions in channels ---
  app.event("app_mention", async ({ event, say }) => {
    await handleMessage(event.channel, event.text, event.user, say, config);
  });

  // --- Handle direct messages ---
  app.event("message", async ({ event, say }) => {
    // Only handle plain user messages in DMs (no subtypes like bot_message)
    if ((event as any).subtype) return;
    if ((event as any).channel_type !== "im") return;
    await handleMessage(
      (event as any).channel,
      (event as any).text ?? "",
      (event as any).user,
      say,
      config,
    );
  });

  await app.start();
  console.log("Slack coding agent is running!");
}

async function handleMessage(
  channel: string,
  text: string,
  user: string | undefined,
  say: (msg: string | { text: string; thread_ts?: string }) => Promise<any>,
  config: Config,
) {
  // Strip the bot mention prefix if present (e.g. "<@U123> do something")
  const userMessage = text.replace(/<@[A-Z0-9]+>\s*/g, "").trim();
  if (!userMessage) return;

  if (busyChannels.has(channel)) {
    await say("I'm still working on a previous request in this channel. Please wait.");
    return;
  }

  busyChannels.add(channel);
  console.log(`\n[${channel}] <${user}> ${userMessage}`);

  // Post a "thinking" indicator
  const thinkingMsg = await say("Working on it...");

  try {
    const result = await runAgent(
      userMessage,
      config.llmProvider,
      config.llmModel,
      config.workspaceDir,
    );

    // Log tool usage
    if (result.toolLog.length > 0) {
      console.log(`  Tools used: ${result.toolLog.length}`);
    }

    // Slack messages are limited to ~4000 chars; split if needed
    const chunks = splitMessage(result.reply, 3900);
    for (const chunk of chunks) {
      await say(chunk);
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`  Error: ${message}`);
    await say(`Something went wrong: ${message}`);
  } finally {
    busyChannels.delete(channel);
  }
}

/**
 * Split a long message into chunks that fit within Slack's limit.
 */
function splitMessage(text: string, maxLen: number): string[] {
  if (text.length <= maxLen) return [text];
  const chunks: string[] = [];
  let remaining = text;
  while (remaining.length > 0) {
    // Try to split at a newline boundary
    let splitAt = remaining.lastIndexOf("\n", maxLen);
    if (splitAt <= 0) splitAt = maxLen;
    chunks.push(remaining.slice(0, splitAt));
    remaining = remaining.slice(splitAt).trimStart();
  }
  return chunks;
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
