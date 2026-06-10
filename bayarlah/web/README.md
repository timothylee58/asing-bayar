# Bayar.lah — Web Share Page

Next.js 16 App Router. Serves `/pay/[billId]` — the public member payment confirmation page linked from WhatsApp.

## Dev

```bash
npm install
cp .env.example .env.local
npm run dev
```

## Deploy

**AWS Amplify (recommended):** connect repo in Amplify console, set root to `web/`, Amplify auto-detects Next.js via `amplify.yml`.

**Docker / App Runner / ECS:** uncomment `output: 'standalone'` in `next.config.ts`, then:
```bash
docker build -f Dockerfile \
  --build-arg NEXT_PUBLIC_SUPABASE_URL=... \
  --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=... \
  --build-arg NEXT_PUBLIC_API_URL=... \
  -t bayarlah-web .
```

See root `README.md` for full steps.
