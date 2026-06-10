# Bayar.lah 💸

> **Split duit, no awkward lah.**

Full-stack mobile-first bill splitting app with gamified payment assignment for Malaysian group culture — hawker runs, trips, housemate expenses, class events.

[![EAS Build](https://github.com/timothylee/bayarlah/actions/workflows/eas-build.yml/badge.svg)](https://github.com/timothylee/bayarlah/actions)
[![CI](https://github.com/timothylee/bayarlah/actions/workflows/ci.yml/badge.svg)](https://github.com/timothylee/bayarlah/actions)

---

## Demo

> _[Demo GIF placeholder — record with `adb screenrecord` after running on device]_

**Flows demonstrated:**
1. Create bill → share WhatsApp link
2. Member confirms payment via share link (no login)
3. Organiser sees real-time progress ring update
4. Play Tangga — animated ladder draw assigns who pays
5. Play Pusing — spinning roulette reveals fate, confetti on result

---

## Architecture

```
┌──────────────────────┐     ┌──────────────────────┐
│  Expo App            │     │  Next.js 16 (AWS)     │
│  iOS + Android       │     │  /pay/[billId]        │
│  mobile/             │     │  web/                 │
└──────────┬───────────┘     └──────────┬────────────┘
           │ REST + WebSocket            │ REST + Realtime
           └────────────┬───────────────┘
                        ▼
           ┌────────────────────────┐
           │  FastAPI (Railway)     │
           │  /api/bills            │
           │  /api/payments         │
           │  /api/game/tangga      │
           │  /api/game/roulette    │
           │  /api/notifications    │
           │  /ws/dashboard/{id}    │
           └──────┬─────────┬───────┘
                  │         │
     ┌────────────▼──┐  ┌───▼──────────────┐
     │  Supabase     │  │  Redis           │
     │  PostgreSQL   │  │  game_state      │
     │  + RLS        │  │  nudge_cooldown  │
     │  + Realtime   │  │  session cache   │
     └───────────────┘  └──────────────────┘
                  │
     ┌────────────▼───────────────┐
     │  Expo Push Service         │
     │  (payment + nudge alerts)  │
     └────────────────────────────┘
```

---

## Stack

| Layer | Technology |
|-------|-----------|
| Mobile | React Native + Expo SDK 56 |
| Navigation | Expo Router (file-based) |
| Animations | Reanimated 3 (Tangga dots, confetti, ring) |
| Wheel | react-native-svg (Pusing wheel at 60fps) |
| Share Page | Next.js 16 App Router + Tailwind CSS v4 |
| Backend | FastAPI (Python 3.11, async) |
| Database | Supabase PostgreSQL + RLS |
| Realtime | WebSocket (WS manager) + Supabase Realtime |
| Cache | Redis (game state, nudge TTL) |
| Auth | Supabase Auth (magic link — organiser only) |
| Push | Expo Push Notification Service |
| Deploy | AWS Amplify / App Runner (web) + Railway (backend) |
| CI/CD | GitHub Actions + EAS Build |

---

## Features

### Bill Management
- Create bill with emoji tag, total amount, participants, due date
- Equal split or gamified mode (Tangga / Pusing)
- Shareable link → no login required for members
- Real-time progress ring via WebSocket
- WhatsApp nudge with 24h rate limit per participant

### 🪜 Tangga (Ladder Game)
Localisation of KakaoTalk's 사다리타기. N players pick lanes on an animated vertical ladder; random horizontal rungs redirect paths; sequential path animation (Reanimated 3, 600ms/segment) reveals each fate. Loser gets "Kena kau lah! 🔥" with haptic. Result locked to Supabase + Redis.

**Algorithm:** Seeded RNG (mulberry32) on client mirrors Python `random.Random(seed)` on server — deterministic, reproducible ladder from the same seed.

### 🎡 Pusing (Roulette)
Spinning wheel with N named segments. Physics: `cubic-bezier(0.17, 0.67, 0.12, 0.99)` deceleration over 4–6 seconds (velocity from server). SVG wheel rendered with react-native-svg; rotation driven by Reanimated 3 shared value. Winner reveal + Reanimated 3 confetti burst.

### Push Notifications
- Organiser notified via Expo Push when member pays
- Member notified on nudge
- Deep-link tap → opens bill screen

---

## Project Structure

```
bayarlah/
├── mobile/                    # Expo app (iOS + Android)
│   ├── app/                   # Expo Router screens
│   │   ├── index.tsx          # Bill list
│   │   ├── create.tsx         # Create bill
│   │   ├── bill/[id].tsx      # Dashboard (WS + real-time)
│   │   ├── tangga.tsx         # Tangga game screen
│   │   └── roulette.tsx       # Pusing roulette screen
│   ├── components/
│   │   ├── AnimatedProgressRing.tsx
│   │   └── Confetti.tsx
│   ├── hooks/
│   │   ├── useDashboardWS.ts  # WebSocket with auto-reconnect
│   │   └── usePushNotifications.ts
│   ├── lib/
│   │   ├── api.ts             # Typed API client
│   │   ├── supabase.ts
│   │   ├── TanggaEngine.ts    # Ladder algorithm (seeded RNG)
│   │   ├── RouletteEngine.ts  # Wheel math + arc paths
│   │   └── notifications.ts
│   └── constants/theme.ts     # Design tokens
├── web/                       # Next.js 16 share page
│   └── app/pay/[billId]/      # Member payment confirmation
├── backend/                   # FastAPI service
│   ├── app/
│   │   ├── api/               # bills, payments, game, ws, notifications
│   │   ├── core/              # config, dependencies, ws_manager
│   │   ├── models/            # Pydantic schemas
│   │   └── services/          # push_service
│   ├── railway.toml
│   └── nixpacks.toml
├── supabase/migrations/       # Schema + RLS + push_tokens
├── .github/workflows/         # CI, EAS Build, Railway deploy
└── docker-compose.yml         # Local dev (FastAPI + Redis)
```

---

## Quick Start

### Prerequisites
- Node.js 20+, Python 3.11+, Docker
- Supabase project (free tier works)
- Expo account (for EAS builds)

### 1 — Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill SUPABASE_URL, SUPABASE_SERVICE_KEY, REDIS_URL
docker compose up -d redis  # start Redis only
uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

### 2 — Database

```sql
-- Run in Supabase SQL editor:
-- supabase/migrations/20260531000001_initial_schema.sql
-- supabase/migrations/20260531000002_push_tokens.sql
```

### 3 — Web Share Page

```bash
cd web
npm install
cp .env.example .env.local  # fill Supabase creds + NEXT_PUBLIC_API_URL
npm run dev
# → http://localhost:3000
```

### 4 — Mobile

```bash
cd mobile
npm install
# Edit app.json extra.supabaseUrl + supabaseAnonKey
npx expo start
# Scan QR with Expo Go app
```

---

## Deployment

### Backend → Railway

```bash
# Push to main → GitHub Actions triggers Railway deploy
# Or manually:
railway login
railway link
railway up --service bayarlah-backend
```

Required Railway env vars:
```
ENV=production
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
REDIS_URL=...  # Railway Redis addon
CORS_ORIGINS=["https://your-amplify-app.amplifyapp.com","https://your-custom-domain.com"]
```

### Web → AWS Amplify (recommended)

**Option A — Git integration (auto-deploy on push):**

1. AWS Console → Amplify → **Create new app** → Connect GitHub repo
2. Select branch `main`, root directory `web/`
3. Amplify detects Next.js and uses `web/amplify.yml` automatically
4. Set environment variables in **App settings → Environment variables**:
   ```
   NEXT_PUBLIC_SUPABASE_URL
   NEXT_PUBLIC_SUPABASE_ANON_KEY
   NEXT_PUBLIC_API_URL
   ```
5. Deploy. Every push to `main` auto-redeploys.

**Option B — Container deploy (App Runner / ECS):**

```bash
# 1. Enable standalone output in web/next.config.ts: output: 'standalone'
# 2. Build + push image
cd web
aws ecr create-repository --repository-name bayarlah-web
docker build \
  --build-arg NEXT_PUBLIC_SUPABASE_URL=... \
  --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=... \
  --build-arg NEXT_PUBLIC_API_URL=... \
  -t bayarlah-web .
docker tag bayarlah-web:latest <account>.dkr.ecr.<region>.amazonaws.com/bayarlah-web:latest
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker push <account>.dkr.ecr.<region>.amazonaws.com/bayarlah-web:latest

# 3. Create App Runner service pointing to the ECR image
# Port: 3000
```

**Required GitHub Actions secrets (for manual trigger workflow):**
```
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
AWS_AMPLIFY_APP_ID
```

### Mobile → EAS

```bash
cd mobile
# 1. Create EAS project
eas init

# 2. Update app.json extra.eas.projectId with your project ID

# 3. Build preview APK
eas build --platform android --profile preview

# 4. Production build
eas build --platform android --profile production
eas build --platform ios --profile production
```

---

## Design System

| Token | Value | Usage |
|-------|-------|-------|
| Brand Red | `#C8410A` | CTAs, loser reveals |
| Turmeric Gold | `#BA7517` | Nudge buttons, mid-progress |
| Forest Green | `#1D9E75` | Paid states, success |
| Dark BG | `#0F0D0B` | Dark mode background |
| Light BG | `#FAFAF8` | Light mode background |
| Motion — Tangga | `ease-in-out 600ms/unit` | Path traversal |
| Motion — Pusing | `cubic-bezier(0.17,0.67,0.12,0.99)` | Wheel deceleration |
| Motion — Ring | `spring(damping:15)` | Progress ring pop |

---

## Portfolio Notes

Built to demonstrate to **Malaysian/Singapore tech employers**:

- **Real-time multiplayer UX** — WebSocket state sync between organiser + members
- **Gamification engineering** — seeded deterministic RNG, path traversal algorithm, physics-based deceleration
- **Mobile-first React Native** — Expo Router, Reanimated 3 native-driver animations, Expo Push
- **Full-stack FastAPI** — async routes, Redis game state, Supabase RLS security
- **Production deployment** — Railway (backend), AWS Amplify / App Runner (web), EAS (mobile), GitHub Actions CI

---

*Bayar.lah — Timothy Lee | May 2026 | [timothylee.dev](https://timothylee.dev)*
