/**
 * Agent loop: sends messages to the LLM via pi-ai and executes tool calls
 * in a loop until the model produces a final text response.
 */

import { getModel, complete, validateToolCall, type Context } from "@mariozechner/pi-ai";
import { allTools, executeTool } from "./tools.js";

const MAX_TOOL_ROUNDS = 25;

export interface AgentResult {
  reply: string;
  toolLog: string[];
}

/**
 * Run the agent loop for a single user message.
 *
 * @param userMessage  The text the user sent in Slack
 * @param provider     pi-ai provider string (e.g. "anthropic")
 * @param modelId      pi-ai model id (e.g. "claude-sonnet-4-20250514")
 * @param workspaceDir Directory where file/bash tools operate
 * @returns The final text reply and a log of tool invocations
 */
export async function runAgent(
  userMessage: string,
  provider: string,
  modelId: string,
  workspaceDir: string,
): Promise<AgentResult> {
  // getModel is typed – we cast the provider/model strings since the user
  // can configure them dynamically.
  const model = getModel(provider as any, modelId as any);

  const context: Context = {
    systemPrompt: buildSystemPrompt(workspaceDir),
    messages: [{ role: "user", content: userMessage, timestamp: Date.now() }],
    tools: allTools,
  };

  const toolLog: string[] = [];

  for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
    const response = await complete(model, context);
    context.messages.push(response);

    // Extract tool calls from the response
    const toolCalls = response.content.filter(
      (block: any) => block.type === "toolCall",
    );

    // If no tool calls, extract text and return
    if (toolCalls.length === 0) {
      const textParts = response.content
        .filter((block: any) => block.type === "text")
        .map((block: any) => block.text);
      return { reply: textParts.join("\n") || "(no response)", toolLog };
    }

    // Execute each tool call and append results
    for (const call of toolCalls) {
      let args: Record<string, unknown>;
      try {
        args = validateToolCall(allTools, call as any);
      } catch {
        args = (call as any).arguments ?? {};
      }

      const toolName = (call as any).name as string;
      const toolCallId = (call as any).id as string;

      toolLog.push(`${toolName}(${JSON.stringify(args)})`);
      console.log(`  [tool] ${toolName}(${summarizeArgs(args)})`);

      const result = await executeTool(toolName, args, workspaceDir);

      context.messages.push({
        role: "toolResult",
        toolCallId,
        toolName,
        content: [{ type: "text", text: truncate(result.text, 30_000) }],
        isError: result.isError,
        timestamp: Date.now(),
      });
    }
  }

  return {
    reply: `Reached the maximum of ${MAX_TOOL_ROUNDS} tool rounds. Please simplify your request.`,
    toolLog,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildSystemPrompt(workspaceDir: string): string {
  return [
    "You are a coding agent operating inside a Slack workspace.",
    "You help users by reading, writing, and editing code, and running shell commands.",
    "",
    `Working directory: ${workspaceDir}`,
    "",
    "Guidelines:",
    "- Use the tools provided to fulfill requests. Prefer small, incremental changes.",
    "- After making changes, verify them (e.g. run tests or read the file back).",
    "- Keep responses concise – Slack messages have a 4000 character limit.",
    "- When showing code, use Slack markdown (```code```).",
    "- If a task is ambiguous, ask a clarifying question instead of guessing.",
  ].join("\n");
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "\n... (truncated)";
}

function summarizeArgs(args: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(args)) {
    const str = String(value);
    parts.push(`${key}: ${str.length > 80 ? str.slice(0, 80) + "..." : str}`);
  }
  return parts.join(", ");
}
