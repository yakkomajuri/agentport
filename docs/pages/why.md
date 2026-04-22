---
title: Why AgentPort exists
nav_title: Why AgentPort exists
---

# Why AgentPort exists

AgentPort exists for people who want to harness the power of Claws and autonomous agents but are rightfully concerned about security.

What we've seen so far is that people generally fall into one of two buckets: the ones that don't care too much about security and are actually getting a lot of value from projects like OpenClaw and the ones that outright refuse to use them due to security concerns.

AgentPort was built for those in the second group to be able to reap the benefits of autonomous agents as well.

So far, the story for connecting third-party tools to agents has been all-or-nothing. You give it access to this because it's not dangerous, but you don't give it access to that. You give it a really restricted API key for a service so it can do a few things but not cause any damage. 

With AgentPort, your agent can have _more_ access because you retain full control. For instance, instead of the agent only being able to research and prepare an email that you then need to copy-paste into an email client and send yourself, it can go as far as preparing the email and sending it, with you just needing to approve the final step. The same principle applies to making a payment, updating production data, and managing tasks in a project.

AgentPort is also about peace of mind. Models are not immune to prompt injection and hallucinations, but we don't expect them to be compromised or hallucinate. So hopefully your agent never exfiltrates an API key, but with AgentPort you can sleep at night knowing it didn't already happen without you even noticing. Even if you never get a request from your agent that you deny, you know at the very least that it couldn't have done anything other than what you approved.

This problem is even more acute at companies that want to incorporate more agentic workflows into their work. Security becomes even more important, and it walks hand-in-hand with compliance. With AgentPort you can safely run agents in production. Our open source version is primarily built for individual use, but if you're interested in building guardrails for deploying agents in production at your company, reach out to `founders@agentport.sh`.