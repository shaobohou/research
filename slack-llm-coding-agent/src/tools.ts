/**
 * Tool definitions and execution for the coding agent.
 *
 * Provides four core tools that the LLM can invoke:
 *   - read_file:  Read the contents of a file
 *   - write_file: Write content to a file (creates or overwrites)
 *   - edit_file:  Replace a specific string in a file
 *   - bash:       Execute a shell command
 */

import { Type, type Tool } from "@mariozechner/pi-ai";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { exec } from "node:child_process";
import { dirname, resolve, isAbsolute } from "node:path";

// ---------------------------------------------------------------------------
// Tool definitions (TypeBox schemas consumed by pi-ai)
// ---------------------------------------------------------------------------

export const readFileTool: Tool = {
  name: "read_file",
  description:
    "Read the contents of a file at the given path. Returns the file text or an error message.",
  parameters: Type.Object({
    path: Type.String({ description: "Absolute or workspace-relative file path" }),
  }),
};

export const writeFileTool: Tool = {
  name: "write_file",
  description:
    "Write content to a file, creating parent directories as needed. Overwrites existing files.",
  parameters: Type.Object({
    path: Type.String({ description: "Absolute or workspace-relative file path" }),
    content: Type.String({ description: "Full file content to write" }),
  }),
};

export const editFileTool: Tool = {
  name: "edit_file",
  description:
    "Replace the first occurrence of `old_string` with `new_string` in a file. " +
    "Fails if `old_string` is not found.",
  parameters: Type.Object({
    path: Type.String({ description: "Absolute or workspace-relative file path" }),
    old_string: Type.String({ description: "Exact text to find" }),
    new_string: Type.String({ description: "Replacement text" }),
  }),
};

export const bashTool: Tool = {
  name: "bash",
  description:
    "Execute a bash command and return its combined stdout + stderr. " +
    "Use this for running tests, installing packages, git operations, etc. " +
    "Commands run inside the workspace directory.",
  parameters: Type.Object({
    command: Type.String({ description: "Shell command to execute" }),
  }),
};

/** All tools the agent can use, in a convenient array. */
export const allTools: Tool[] = [readFileTool, writeFileTool, editFileTool, bashTool];

// ---------------------------------------------------------------------------
// Tool execution
// ---------------------------------------------------------------------------

function resolvePath(path: string, workspaceDir: string): string {
  if (isAbsolute(path)) return path;
  return resolve(workspaceDir, path);
}

function execCommand(command: string, cwd: string): Promise<string> {
  return new Promise((resolve) => {
    exec(command, { cwd, timeout: 60_000, maxBuffer: 1024 * 1024 }, (err, stdout, stderr) => {
      const output = (stdout + stderr).trim();
      if (err && !output) {
        resolve(`Error: ${err.message}`);
      } else {
        resolve(output || "(no output)");
      }
    });
  });
}

/**
 * Execute a tool call and return a text result.
 */
export async function executeTool(
  toolName: string,
  args: Record<string, unknown>,
  workspaceDir: string,
): Promise<{ text: string; isError: boolean }> {
  try {
    switch (toolName) {
      case "read_file": {
        const filePath = resolvePath(args.path as string, workspaceDir);
        const content = await readFile(filePath, "utf-8");
        return { text: content, isError: false };
      }

      case "write_file": {
        const filePath = resolvePath(args.path as string, workspaceDir);
        await mkdir(dirname(filePath), { recursive: true });
        await writeFile(filePath, args.content as string, "utf-8");
        return { text: `Wrote ${filePath}`, isError: false };
      }

      case "edit_file": {
        const filePath = resolvePath(args.path as string, workspaceDir);
        const original = await readFile(filePath, "utf-8");
        const oldStr = args.old_string as string;
        const newStr = args.new_string as string;
        if (!original.includes(oldStr)) {
          return { text: `Error: old_string not found in ${filePath}`, isError: true };
        }
        const updated = original.replace(oldStr, newStr);
        await writeFile(filePath, updated, "utf-8");
        return { text: `Edited ${filePath}`, isError: false };
      }

      case "bash": {
        const output = await execCommand(args.command as string, workspaceDir);
        return { text: output, isError: false };
      }

      default:
        return { text: `Unknown tool: ${toolName}`, isError: true };
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return { text: `Error: ${message}`, isError: true };
  }
}
