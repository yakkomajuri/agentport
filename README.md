# AgentPort

AgentPort is an open source gateway to securely connect any service to autonomous agents.

"Securely" means that agents never see your API keys, and that you control exactly what they can and can't do with approval policies.

Currently, the approval policies supported are:

* **Auto-approve**: The agent can call the tool any time and it will run automatically.
* **Ask for approval**: When trying to call the tool the agent will get back a link that only you as a logged in user can approve. You will be approving the tool being called as well as the exact parameters so you retain full control. e.g. if you approve `create_refund` on Stripe with params `customerId=1234` and `amount=15` the agent can't then change the customer ID or the amount.
* **Deny**: The agent can never use this tool.

