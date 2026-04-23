# AgentPort

AgentPort is an open source gateway to securely connect any service to autonomous agents.

Securely means that agents never see your API keys, and that you control exactly what they can and can't do with approval policies.

## 🚀 Get started

### Try locally

```sh
git clone https://github.com/yakkomajuri/agentport

cd agentport
docker compose up
```

### Production self-hosted deploy

```sh
curl -fsSL https://install.agentport.sh | sh
```

### Cloud

[app.agentport.sh](https://app.agentport.sh)

## Approval policies

Currently, the supported approval policies are:

* **Auto-approve**: The agent can call the tool any time and it will run automatically.
* **Ask for approval**: When trying to call the tool the agent will get back a link that only you as a logged in user can approve. You will be approving the tool being called as well as the exact parameters so you retain full control. e.g. if you approve `create_refund` on Stripe with params `customerId=1234` and `amount=15` the agent can't then change the customer ID or the amount.
* **Deny**: The agent can never use this tool.

When you set a tool on AgentPort to have a policy of "Ask for approval", any time your agent tries to call that tool via the CLI or the MCP it will get a response back explaining that this tool is gated and that it requires human approval, as well as link to send to you for approval.


