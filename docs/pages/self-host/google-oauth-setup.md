---
title: Google OAuth Setup
---

# Google OAuth Setup

The Gmail and Google Calendar integrations share a single Google OAuth app. You create it once and both integrations use the same credentials.

## 1. Create a project in Google Cloud Console

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and sign in.
2. Click the project selector at the top → **New Project**.
3. Give it a name (e.g. `AgentPort`) and click **Create**.

## 2. Enable the APIs

From the left sidebar go to **APIs & Services → Library** and enable both:

- **Gmail API** — search "Gmail API"
- **Google Calendar API** — search "Google Calendar API"

Click **Enable** on each.

## 3. Configure the OAuth consent screen

The consent screen wizard has four steps: **App info → Scopes → Test users → Summary**.

**App info:**
1. Go to **APIs & Services → OAuth consent screen**.
2. Choose **External** (or Internal if this is a Google Workspace org where all users are in the same org).
3. Fill in the required fields:
   - **App name** — anything, e.g. `AgentPort`
   - **User support email** — your email
   - **Developer contact email** — your email
4. Click **Save and Continue**.

**Scopes:**
1. Click **Add or Remove Scopes**.
2. Paste each scope into the filter box and check it:
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/calendar`
3. Click **Update** to confirm, then **Save and Continue**.

**Test users:**
Add the Google account(s) that will connect to AgentPort. While the app is in Testing mode only these accounts can authorize — you can leave it in Testing indefinitely for personal or team use.

Click **Save and Continue**, then **Back to Dashboard**.

## 4. Create OAuth credentials

1. Go to **APIs & Services → Credentials**.
2. Click **+ Create Credentials → OAuth client ID**.
3. Set **Application type** to **Web application**.
4. Give it a name, e.g. `AgentPort`.
5. Under **Authorized redirect URIs**, add the value that matches your deployment:

   - **Self-hosted on a domain:** `https://agentport.example.com/api/auth/callback`
   - **Local development:** `http://localhost:4747/api/auth/callback`

   You can add both if you develop locally and also run a production deployment — they just need to match the `OAUTH_CALLBACK_URL` environment variable exactly.
6. Click **Create**.

Google will show you a **Client ID** and **Client secret** — copy both.

## 5. Set the environment variables

```bash
export OAUTH_GOOGLE_CLIENT_ID="<your client id>"
export OAUTH_GOOGLE_CLIENT_SECRET="<your client secret>"
```

Or add them to your `.env` file:

```
OAUTH_GOOGLE_CLIENT_ID=<your client id>
OAUTH_GOOGLE_CLIENT_SECRET=<your client secret>
```

Both Gmail and Google Calendar will become available in the integrations UI once these are set.

## Notes

**Refresh tokens** — The OAuth flow requests `access_type=offline` and `prompt=consent`, so Google issues a refresh token on first authorization. Tokens are refreshed automatically when they expire.

**Testing vs. Published** — Apps in Testing mode only allow the test users you explicitly add. For personal or team use this is fine indefinitely. To allow any Google account to connect, submit the app for verification (required when using sensitive scopes like Gmail and Calendar).

**Callback URL in production** — If you deploy AgentPort to a non-localhost URL, add that callback URL to the **Authorized redirect URIs** list in your OAuth client and set `OAUTH_CALLBACK_URL` accordingly. You can have multiple redirect URIs registered on the same client.
