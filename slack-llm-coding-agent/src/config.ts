/**
 * Configuration for the Slack LLM coding agent.
 *
 * Required environment variables:
 *   SLACK_BOT_TOKEN     - Slack Bot User OAuth Token (xoxb-...)
 *   SLACK_APP_TOKEN     - Slack App-Level Token for Socket Mode (xapp-...)
 *   ANTHROPIC_API_KEY   - Anthropic API key (or use another provider's key)
 *
 * Optional:
 *   LLM_PROVIDER        - pi-ai provider name (default: "anthropic")
 *   LLM_MODEL           - pi-ai model id (default: "claude-sonnet-4-20250514")
 *   WORKSPACE_DIR       - Working directory for the agent (default: cwd)
 */

export interface Config {
  slackBotToken: string;
  slackAppToken: string;
  llmProvider: string;
  llmModel: string;
  workspaceDir: string;
}

export function loadConfig(): Config {
  const slackBotToken = process.env.SLACK_BOT_TOKEN;
  const slackAppToken = process.env.SLACK_APP_TOKEN;

  if (!slackBotToken) {
    throw new Error("Missing SLACK_BOT_TOKEN environment variable");
  }
  if (!slackAppToken) {
    throw new Error("Missing SLACK_APP_TOKEN environment variable");
  }

  return {
    slackBotToken,
    slackAppToken,
    llmProvider: process.env.LLM_PROVIDER ?? "anthropic",
    llmModel: process.env.LLM_MODEL ?? "claude-sonnet-4-20250514",
    workspaceDir: process.env.WORKSPACE_DIR ?? process.cwd(),
  };
}
