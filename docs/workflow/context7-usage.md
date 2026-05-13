# Context7 usage cheat sheet

Use Context7 for current library, framework, SDK, CLI, cloud-service, and MCP
documentation. Do not use it for local RiftReader debugging, business-logic
review, code review, or repo-specific refactors; inspect the repo directly for
those.

Context7 is advisory external-doc context. It does not prove current RiftReader
truth. Local repo files, tests, build output, git history, capture artifacts, and
fresh PID/HWND/process evidence remain authoritative.

## Default workflow

1. Resolve the library ID first:
   - tool: `resolve-library-id`
   - inputs: `libraryName` plus the user's full question
2. Pick the best `/org/project` match:
   - exact or closest package name
   - official/high-reputation source
   - enough snippets/docs coverage
   - version-specific ID when the user names a version
3. Query docs:
   - tool: `query-docs`
   - inputs: selected `libraryId` plus the user's full question
4. Answer from the fetched docs and state the Context7 ID used when accuracy
   matters.

If the user already provides an exact ID such as `/dotnet/docs`, skip the
resolve step and query that ID directly.

## Common IDs for this repo

| Need | Context7 ID | Notes |
|---|---|---|
| .NET CLI / C# / SDK docs | `/dotnet/docs` | Primary ID for SDK, CLI, C#, build/test docs. |
| PowerShell docs | `/microsoftdocs/powershell-docs` | Use for `pwsh`, execution policy, cmdlet, and scripting syntax docs. |
| Playwright docs | `/microsoft/playwright` | Official Microsoft Playwright source; use for test runner and tracing docs. |
| MCP spec / schema docs | `/modelcontextprotocol/modelcontextprotocol` | Use for current Model Context Protocol schema/tool-contract questions. |
| MCP website docs | `/websites/modelcontextprotocol` | Use for higher-level MCP concepts and current workflow docs. |
| Context7 docs | `/websites/context7` | Use when checking Context7 usage itself. |

## Ready-to-use prompt patterns

```text
Use Context7: current .NET CLI syntax for dotnet test filters.
```

```text
Use Context7 with /dotnet/docs: current .NET 10 SDK CLI behavior for build, test, and solution files.
```

```text
Use Context7 with /dotnet/docs: can dotnet build target a .slnx solution?
```

```text
Use Context7: current PowerShell 7 pwsh -File syntax and execution policy behavior.
```

```text
Use Context7: current Playwright tracing config for failed tests.
```

```text
Use Context7 with /modelcontextprotocol/modelcontextprotocol: current MCP tool schema and JSON-RPC contract.
```

```text
Use Context7 with /websites/modelcontextprotocol: current MCP server/client setup guidance.
```

## Current smoke-test notes

- `.NET`: `/dotnet/docs` confirmed `dotnet restore`, `dotnet build`, and
  `dotnet test` are standard CLI commands for restore/build/test workflows.
- `.slnx`: `/dotnet/docs` confirmed `dotnet sln` supports `.sln` and `.slnx`;
  current `dotnet new sln` documentation notes newer SDKs create `.slnx`.
- `PowerShell`: `/microsoftdocs/powershell-docs` confirmed `pwsh` supports
  `-File` and session-scoped `-ExecutionPolicy`.
- `Playwright`: `/microsoft/playwright` confirmed trace modes including
  `on`, `on-first-retry`, `retain-on-failure`, and
  `retain-on-first-failure`.
- `MCP`: `/modelcontextprotocol/modelcontextprotocol` and
  `/websites/modelcontextprotocol` are high-reputation Context7 matches for MCP
  spec/schema and website-level docs.

## RiftReader-specific guidance

For this repo, prefer Context7 before:

- changing `.NET` SDK/CLI behavior;
- updating dependency or package guidance;
- adding Playwright/browser-test examples;
- changing MCP client/server/tool-contract examples;
- documenting PowerShell syntax or execution-policy behavior;
- answering version-sensitive library/API questions.

Do not use Context7 as a replacement for:

- reading `agents.md`;
- inspecting current `RiftReader.slnx` contents;
- debugging local scripts, C# projects, or live RIFT tooling;
- validating live PID/HWND/input behavior;
- proving x64dbg candidates, coordinate truth, or process-memory chains.
