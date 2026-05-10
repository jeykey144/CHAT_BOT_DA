# Deploy TOSE + AWS RDS Checklist

Use this checklist when TOSE build succeeds but the public URL returns Bad Gateway or the app shows a MySQL timeout.

## Required environment variables

Set these values on TOSE, not only in local `.env`:

```env
AUTH_DB_URL=mysql+pymysql://root:<password>@mysql-chatbot.c3igik0cizol.ap-southeast-1.rds.amazonaws.com:3306/chatbot?charset=utf8mb4
LLM_PROVIDER=groq
GROQ_API_KEY=<groq-api-key>
GROQ_MODEL=llama-3.3-70b-versatile
COOKIE_SECRET=<long-random-secret>
DB_CONNECT_TIMEOUT_S=10
DB_POOL_TIMEOUT_S=10
```

Important: the RDS database name verified from local checks is `chatbot`. Do not use `chatbot_auth` unless that database has been created on RDS.

## RDS network access

If TOSE logs show:

```text
(2003, "Can't connect to MySQL server ... (timed out)")
```

the app can start, but TOSE cannot reach RDS on TCP port 3306. Fix AWS networking:

1. Open AWS Console -> RDS -> `mysql-chatbot`.
2. Confirm DB status is `Available`.
3. In Connectivity & security, confirm the DB is publicly reachable if TOSE is outside AWS/VPC.
4. Open the RDS VPC security group.
5. Add an inbound rule:

```text
Type: MySQL/Aurora
Protocol: TCP
Port: 3306
Source: TOSE outbound IP/CIDR
```

For a short connectivity test only, use `0.0.0.0/0`, redeploy/restart TOSE, then replace it with a narrower source as soon as possible.

## Deploy flow

From the repository root:

```powershell
tose env push .\AI-Datanalysis-main\.env
tose deploy
tose logs -f
```

If `tose env push` is not available in your CLI version, set the same variables in the TOSE dashboard or with `tose env set`.

## Expected result

- Docker listens on the platform-provided `PORT` when TOSE injects it.
- Health check uses the same `PORT`.
- If RDS is blocked, the Streamlit page now shows a deployment error with hints instead of an unhandled traceback.
