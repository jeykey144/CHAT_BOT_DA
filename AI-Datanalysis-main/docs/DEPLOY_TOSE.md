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

When entering variables in the TOSE dashboard, use separate key/value fields:

```text
Key:   AUTH_DB_URL
Value: mysql+pymysql://root:<url-encoded-password>@mysql-chatbot.c3igik0cizol.ap-southeast-1.rds.amazonaws.com:3306/chatbot?charset=utf8mb4
```

Do not put `AUTH_DB_URL=` inside the value field. Do not wrap the value in quotes, backticks, or angle brackets.

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

## MySQL authentication

If TOSE logs show:

```text
(1045, "Access denied for user 'root'@'<ip>' (using password: YES)")
```

the network path is open and RDS is receiving the connection. The problem is now MySQL authentication or user permission.

Fix it in this order:

1. Verify `AUTH_DB_URL` on TOSE uses the current RDS password, not an old local password.
2. Verify the database name is `chatbot`.
3. If the password contains special URL characters such as `@`, `#`, `%`, `:`, `/`, `?`, `&`, or `+`, URL-encode the password before placing it in `AUTH_DB_URL`.
4. Prefer creating a dedicated MySQL user for the app instead of using `root`.

Example dedicated app user:

```sql
CREATE USER 'ai_app'@'%' IDENTIFIED BY '<strong-password>';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
ON chatbot.* TO 'ai_app'@'%';
FLUSH PRIVILEGES;
```

Then set TOSE:

```env
AUTH_DB_URL=mysql+pymysql://ai_app:<url-encoded-password>@mysql-chatbot.c3igik0cizol.ap-southeast-1.rds.amazonaws.com:3306/chatbot?charset=utf8mb4
```

The IP in the error message, for example `103.2.227.166`, is the client IP seen by MySQL. If this IP belongs to TOSE, use `103.2.227.166/32` in the RDS security group instead of leaving `0.0.0.0/0` open.

## URL parse errors

If the app shows:

```text
Could not parse SQLAlchemy URL from given URL string
```

then `AUTH_DB_URL` is malformed on TOSE. Common mistakes:

- The value field contains `AUTH_DB_URL=mysql+pymysql://...` instead of only `mysql+pymysql://...`.
- The value is wrapped in quotes, backticks, or angle brackets.
- The password still contains placeholder text such as `<password>`.
- The password contains reserved URL characters and was not URL-encoded.
- The value was pasted with a line break or hidden leading/trailing spaces.

Correct value format:

```text
mysql+pymysql://root:<url-encoded-password>@mysql-chatbot.c3igik0cizol.ap-southeast-1.rds.amazonaws.com:3306/chatbot?charset=utf8mb4
```

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
