# Acme Approvals

A small fictional SaaS product for AI Lab Keys demos. A prospect points Claude Code at it through an MCP server, changes settings in plain English, and the admin UI updates on the other half of the screen within two seconds.

Everything runs inside the VM on localhost. Nothing leaves the machine except the AI key's calls to the model provider.

## What is in the folder

| File | What it is |
|---|---|
| `app.py` | The product. Web UI on `/`, REST API under `/api`, OpenAPI docs on `/docs`. SQLite database `acme.db` is created on first run with demo data. |
| `mcp_server.py` | MCP server Claude Code connects to. Ten tools, each calling the app's API, so agent actions show in the UI's Activity feed tagged `prospect-agent`. |
| `.mcp.json` | Tells Claude Code to start the MCP server when it opens this folder. |
| `CLAUDE.md` | Project instructions Claude Code reads on start. Keeps it from editing the product's source. |
| `install.sh` | One-shot install inside the VM: installs packages, starts the app, adds an at-boot entry. |
| `run.sh` / `run.ps1` | Install requirements and start the app in the background (Linux and Windows). |

## Install in the VM (Linux)

From a terminal in VS Code, in your home directory:

```
git clone https://github.com/matherbe/acme-approvals ~/acme-approvals
bash ~/acme-approvals/install.sh
cd ~/acme-approvals && code -r . && claude
```

Or hand the first two lines to Claude Code as a prompt and let it run them.

Claude Code asks whether to trust the `acme-approvals` MCP server. Say yes, then `/mcp` should list it as connected with ten tools.

Windows: clone to `%USERPROFILE%\acme-approvals`, run `run.ps1`, and change `python3` to `python` in `.mcp.json`.

## Seeing the UI

The VM in the demo Template has no desktop; VS Code is served in the browser. That is fine. Open the Command Palette, run **Simple Browser: Show**, and enter `http://localhost:8080/`. It opens as an editor tab inside VS Code. Drag that tab into a second editor group, or right-click the terminal panel header and choose **Move Panel Right**, so the terminal and the UI sit side by side. The UI uses relative URLs, so it works behind the proxy path web VS Code uses for localhost.

Fallback if you have a separate virtual browser VM in the same environment: start the app on the app VM with `ACME_HOST=0.0.0.0 bash ~/acme-approvals/run.sh` and browse to `http://<app VM private IP>:8080/` from the browser VM.

### Optional: give the product its own API key

Set `ACME_API_KEY=some-token` in the environment before starting both the app and Claude Code. The API then requires `X-API-Key`, the MCP server sends it automatically, and the UI reads it from `http://localhost:8080/?key=some-token`. This lets Credential Manager issue the product's key per session alongside the AI key: two credentials, one launch, both scoped to the person.

## Demo script

Prompts that show well, in order. Each one produces a visible change.

1. `What approval workflows does Acme have, and who approves what?` (read-only, proves the connection)
2. `Raise the software purchases approval threshold to $5,000, turn on requester notifications for contractor onboarding, and approve the pending JetBrains request.` (two cards flash, one row leaves pending, three feed lines)
3. `Create a workflow called "Hardware over $10k", approved by the CFO, threshold ten thousand dollars.` (new card appears)
4. `Reject the contract SRE request and tell me what's still pending.` (pending list shrinks)
5. `Pause the travel workflow while finance reviews it.` (badge flips to Paused)

Then send one more prompt after the budget is spent, and the agent stops while the product keeps running.

## Between takes

`curl -X POST http://localhost:8080/api/reset` puts the demo data back. Or delete `acme.db` and restart the app.

## Notes

Acme Inc, the people and the requests are invented. Amounts are USD. The app listens on 127.0.0.1 by default (`ACME_HOST=0.0.0.0` to expose it inside the environment); change `ACME_PORT` if 8080 is taken.
