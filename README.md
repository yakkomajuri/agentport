# AgentPort

AgentPort is an open source gateway to securely connect any service to autonomous agents 🦞.

![agentport-diagram (2).png](/assets/1777315695147-agentport-diagram-\(2\).png)

## 🚀 Get started

### Try locally

Clone the repo and run:

```sh
docker compose up
```

### Production self-hosted deploy

```sh
curl -fsSL https://install.agentport.sh | sh
```

See the [docs](https://docs.agentport.sh/self-host/install) for complete instructions.

### Cloud

[app.agentport.sh](https://app.agentport.sh)

## About

AgentPort lets you connect any service to your agent or claw securely.

Securely means that agents never see your API keys, and that you control exactly what they can and can't do with approval policies.

AgentPort ships with 50 integrations out of the box like Stripe, PostHog, GitHub, Gmail, Google Calendar, and a lot more are coming. Connecting to an integration takes a few clicks and it immediately makes it available to your agents, wherever AgentPort is connected.

You can then choose exactly what the agent can and can't do, as well as what tools it can use only with your approval. For example, `search_emails` on Gmail can be set to "Auto-approve", with `send_email` being set to "Ask for approval". On Stripe, you could have the agent auto-run `get_customer` but require your approval to run `create_refund`.

Agents connect to AgentPort using either our [CLI](https://docs.agentport.sh/connect/cli) or our [MCP](https://docs.agentport.sh/connect/mcp).

![Approval policies](/raw/docs/static/img/approval-policies.png)

## Philosophy

AgentPort's goal is to let you deploy autonomous agents securely. By adding a security layer, our goal is to enable you to give your agents **more power.**

Today we mostly follow all-or-nothing approaches: we give agents full access to a service or we don't give them access at all.

With AgentPort, you can give your agents more tools that they can use when perfoming tasks for you, but ensuring they don't do anything dangerous.

That way, you can give them access to Stripe, your email, and even bank APIs, so they can do work in an automated way, loop you in when needed, and then get right back to it.

For instance, they gather all the information they need to send an email on your behalf and then you can let them send it with one click, rather than copy-pasting output, going to your email client, and sending it yourself.

## Approval policies

Currently, the supported approval policies are:

* **Auto-approve**: The agent can call the tool any time and it will run automatically.
* **Ask for approval**: When trying to call the tool the agent will get back a link that only you as a logged in user can approve. You will be approving the tool being called as well as the exact parameters so you retain full control. e.g. if you approve `create_refund` on Stripe with params `customerId=1234` and `amount=15` the agent can't then change the customer ID or the amount.
* **Deny**: The agent can never use this tool.

When you set a tool on AgentPort to have a policy of "Ask for approval", any time your agent tries to call that tool via the CLI or the MCP it will get a response back explaining that this tool is gated and that it requires human approval, as well as link to send to you where you can approve the tool call based on the exact parameters.

![Screenshot 2026-04-27 at 15.53.02.png](/assets/1777315990898-Screenshot-2026-04-27-at-15.53.02.png)

P.S. You should probably deny requests like the one above.

## Logs

Another key part of AgentPort is that **everything**'s logged.

We log when a request to use a tool happened, when it was approved, the IP the request came from and the IP that approved it and so on.

This means you have full visibility into what your agents are doing and how they work, as well as have complete logs for auditability and compliance purposes.

![Logs](/raw/docs/static/img/logs.png)

## Connecting agents

Your agents can connect to AgentPort using our MCP server:

```text
https://app.agentport.sh/mcp
```

> Or `https://<your-domain>/mcp` if you're self-hosting.

And they can also use our CLI, installable with `npm install -g agentport-cli` .

You should also definitely be using the [AgentPort skills](https://github.com/yakkomajuri/agentport-skills) in order for agents to use AgentPort most effectively:

```bash
npx skills add yakkomajuri/agentport-skills
```

## Docs

Full documentation lives at [docs.agentport.sh](https://docs.agentport.sh) — covering the REST API, the MCP aggregator, approval flows, self-hosting, and agent-specific setup guides.

## License

MIT
