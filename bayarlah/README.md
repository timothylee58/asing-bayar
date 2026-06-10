# Bayar.lah 💸

> **Split duit, no awkward lah.**

A production-grade, mobile-first bill splitting app built for Malaysian group culture — hawker runs, trips, housemate expenses, class events. Features gamified payment assignment via animated ladder draws and roulette wheels, real-time WebSocket dashboards, and Expo push notifications.

[![CI](https://github.com/timothylee58/bayarlah/actions/workflows/ci.yml/badge.svg)](https://github.com/timothylee58/bayarlah/actions/workflows/ci.yml)
[![EAS Build](https://github.com/timothylee58/bayarlah/actions/workflows/eas-build.yml/badge.svg)](https://github.com/timothylee58/bayarlah/actions/workflows/eas-build.yml)
[![Railway Deploy](https://github.com/timothylee58/bayarlah/actions/workflows/railway-deploy.yml/badge.svg)](https://github.com/timothylee58/bayarlah/actions/workflows/railway-deploy.yml)

---

## Table of Contents

- [Demo](#demo)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Local Development](#local-development)
- [Environment Variables](#environment-variables)
- [Database Setup](#database-setup)
- [Deployment](#deployment)
- [API Reference](#api-reference)
- [Game Algorithms](#game-algorithms)
- [Design System](#design-system)
- [CI/CD Pipeline](#cicd-pipeline)
- [Portfolio Notes](#portfolio-notes)

---

## Demo

> _Demo GIF — record with `adb screenrecord` after running on device_

**User flows:**

| Flow | Description |
|------|-------------|
| 1 | Organiser creates bill → WhatsApp share link generated |
| 2 | Member opens share link → confirms payment (no login required) |
| 3 | Organiser sees real-time progress ring update via WebSocket |
| 4 | Play **Tangga** — animated ladder draw assigns who pays |
| 5 | Play **Pusing** — spinning roulette reveals fate, confetti on result |
| 6 | Push notification fires when member confirms payment |
| 7 | WhatsApp nudge sent with 24h rate limit per participant |

---

## Features

### Bill Management
- Create bill with emoji tag, total amount (MYR), participants, due date
- Equal split **or** gamified mode (Tangga / Pusing assigns payer)
- Shareable payment link — members confirm without an account
- Real-time progress ring (WebSocket, no polling)
- WhatsApp deeplink nudge with 24h Redis cooldown per participant

### 🪜 Tangga — Ladder Game
Localisation of KakaoTalk's 사다리타기. N players pick lanes on an animated vertical ladder; random horizontal rungs redirect paths; sequential path animation (Reanimated 3, 600ms/segment) reveals each fate. Loser gets **"Kena kau lah! 🔥"** with haptic feedback. Result locked atomically to Supabase + Redis.

- **Algorithm:** Seeded RNG (mulberry32) on the TypeScript client mirrors Python `random.Random(seed)` on the server — deterministic, reproducible ladder from the same seed
- **Fairness:** Rungs generated server-side, seed committed before reveal — no client manipulation possible
- **Replay:** Same seed always produces the same ladder — shareable and auditable

### 🎡 Pusing — Roulette Wheel
Spinning wheel with N named segments. Physics: `cubic-bezier(0.17, 0.67, 0.12, 0.99)` deceleration over 4–6 seconds. SVG wheel rendered with `react-native-svg`; rotation driven by Reanimated 3 shared value. Winner reveal + confetti burst.

- **Segments:** Auto-calculated arc paths from participant count
- **Result:** Server-computed before animation starts — visually exciting, not manipulable
- **Labels:** Clipped SVG text centred on each segment arc

### Push Notifications
- Organiser notified via Expo Push when any member pays
- Member notified when nudged
- Deep-link tap → opens the relevant bill screen directly

---

## Architecture

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│  Expo App (iOS + Android)   │     │  Next.js 16 (AWS App Runner) │
│  Expo Router file-based nav │     │  /pay/[billId]               │
│  Reanimated 3 animations    │     │  Supabase Realtime           │
│  react-native-svg wheel     │     │  No-login payment confirm    │
│  mobile/                    │     │  web/                        │
└────────────┬────────────────┘     └───────────────┬──────────────┘
             │ REST + WebSocket                      │ REST + Realtime
             └─────────────────┬────────────────────┘
                               ▼
              ┌────────────────────────────────┐
              │  FastAPI (Railway)             │
              │  /api/bills                   │
              │  /api/payments                │
              │  /api/game/tangga             │
              │  /api/game/roulette           │
              │  /api/notifications           │
              │  /ws/dashboard/{bill_id}      │
              │  Async Python 3.11            │
              │  Pydantic v2 schemas          │
              └───────┬────────────┬──────────┘
                      │            │
         ┌────────────▼──┐   ┌─────▼────────────────┐
         │  Supabase     │   │  Redis               │
         │  PostgreSQL   │   │  game_state (lock)   │
         │  + RLS        │   │  nudge_cooldown TTL  │
         │  + Realtime   │   │  session cache       │
         │  + Auth       │   └──────────────────────┘
         └───────┬───────┘
                 │
  ┌──────────────▼─────────────────┐
  │  Expo Push Notification Service │
  │  exp.host/--/api/v2/push/send  │
  │  payment + nudge alerts        │
  └─────────────────────────────────┘
```

### Data Flow — Bill Payment (Happy Path)

```
Member              Web (/pay)           FastAPI           Supabase        Organiser App
  │                     │                   │                  │                 │
  ├─ Open share link ──►│                   │                  │                 │
  │                     ├─ GET /bills/{id} ►│                  │                 │
  │                     │◄─ bill + parts ───┤                  │                 │
  ├─ Confirm payment ──►│                   │                  │                 │
  │                     ├─ POST /payments ─►│                  │                 │
  │                     │                  ├─ INSERT payment ─►│                 │
  │                     │                  ├─ WS broadcast ─────────────────────►│
  │                     │                  ├─ Push notify ──────────────────────►│
  │                     │◄─ 200 confirmed ──┤                  │                 │
  ├─ "Payment confirmed"◄┤                  │                  │                 │
```

### WebSocket Event Types

| Event | Direction | Payload |
|-------|-----------|---------|
| `init` | Server → Client | Full bill state on connect |
| `payment_confirmed` | Server → Client | `{ participant_id, paid_at, total_paid, total_amount }` |
| `ping` / `pong` | Bidirectional | Keepalive every 30s |

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Mobile framework | React Native + Expo | SDK 56 |
| Navigation | Expo Router (file-based) | 4.x |
| Animations | Reanimated 3 | 3.x |
| Roulette wheel | react-native-svg | Latest |
| Share page | Next.js App Router | 16.2.6 |
| Styling | Tailwind CSS | v4 |
| Backend | FastAPI (Python, async) | 0.115+ |
| Schema validation | Pydantic | v2 |
| Database | Supabase PostgreSQL | 15 |
| Realtime | Supabase Realtime + WebSocket | — |
| Row Level Security | Supabase RLS policies | — |
| Auth | Supabase Auth (magic link) | — |
| Cache / locks | Redis | 7 |
| Push notifications | Expo Push Notification Service | — |
| Containerisation | Docker + Docker Compose | — |
| Backend deploy | Railway (nixpacks) | — |
| Web deploy | AWS App Runner via ECR | — |
| Mobile build | EAS Build | — |
| CI/CD | GitHub Actions | — |

---

## Project Structure

```
bayarlah/
├── mobile/                         # Expo SDK 56 app
│   ├── app/                        # Expo Router screens
│   │   ├── _layout.tsx             # Root layout — AppShell, push hook
│   │   ├── index.tsx               # Bill list + FAB
│   │   ├── create.tsx              # Create bill (emoji, split mode, participants)
│   │   ├── bill/
│   │   │   └── [id].tsx            # Dashboard — WS, progress ring, nudge
│   │   ├── tangga.tsx              # Tangga ladder game screen
│   │   └── roulette.tsx            # Pusing roulette screen
│   ├── components/
│   │   ├── AnimatedProgressRing.tsx # Border-based ring, spring pop on payment
│   │   └── Confetti.tsx            # 28 Reanimated 3 particles, 3.5s lifetime
│   ├── hooks/
│   │   ├── useDashboardWS.ts       # WebSocket with 3s auto-reconnect
│   │   └── usePushNotifications.ts # Token registration + deep-link handler
│   ├── lib/
│   │   ├── api.ts                  # Typed API client (all endpoints)
│   │   ├── supabase.ts             # AsyncStorage-backed Supabase client
│   │   ├── TanggaEngine.ts         # Ladder algorithm — mulberry32 seeded RNG
│   │   ├── RouletteEngine.ts       # Wheel math — arc paths, label positions
│   │   └── notifications.ts        # Expo push token registration
│   ├── constants/
│   │   └── theme.ts                # Colors, Radius, Spacing, EMOJI_TAGS
│   ├── types/index.ts              # Bill, Participant, Payment, GameResult
│   ├── app.json                    # Expo config — scheme, plugins, EAS projectId
│   ├── eas.json                    # EAS profiles (dev/preview/production)
│   └── babel.config.js             # Reanimated plugin (must be last)
│
├── web/                            # Next.js 16 share page
│   ├── app/
│   │   ├── layout.tsx              # Root layout — OG tags, metadata
│   │   ├── page.tsx                # Landing page
│   │   ├── not-found.tsx
│   │   └── pay/
│   │       └── [billId]/
│   │           ├── page.tsx        # Server component — generateMetadata
│   │           └── PayClientPage.tsx # Client — Realtime, 3-step payment flow
│   ├── lib/supabase.ts             # Supabase browser client
│   ├── types/index.ts
│   ├── amplify.yml                 # AWS Amplify build spec (alt. Option A)
│   ├── Dockerfile                  # Multi-stage — App Runner / ECS
│   └── next.config.ts              # standalone output enabled
│
├── backend/                        # FastAPI service
│   ├── app/
│   │   ├── main.py                 # App factory — CORS, routers
│   │   ├── api/
│   │   │   ├── bills.py            # CRUD + share link
│   │   │   ├── payments.py         # Confirm + nudge — WS broadcast + push
│   │   │   ├── game.py             # Tangga generate/lock, Roulette spin/lock
│   │   │   ├── ws.py               # WebSocket endpoint — init + ping
│   │   │   └── notifications.py    # Push token register/unregister
│   │   ├── core/
│   │   │   ├── config.py           # pydantic-settings — all env vars
│   │   │   ├── dependencies.py     # get_supabase, get_redis, get_current_user
│   │   │   └── ws_manager.py       # ConnectionManager singleton
│   │   ├── models/
│   │   │   ├── bill.py             # BillCreate, BillResponse, etc.
│   │   │   ├── payment.py          # PaymentConfirm, NudgeRequest
│   │   │   ├── game.py             # TanggaResult, RouletteResult, GameState
│   │   │   └── notification.py     # PushTokenRegister
│   │   └── services/
│   │       └── push_service.py     # send_expo_push(), get_participant_tokens()
│   ├── tests/
│   ├── Dockerfile
│   ├── railway.toml
│   ├── nixpacks.toml
│   └── requirements.txt
│
├── supabase/
│   └── migrations/
│       ├── 20260531000001_initial_schema.sql  # bills, participants, payments, game_results + RLS
│       └── 20260531000002_push_tokens.sql     # push_tokens table + RLS
│
├── .github/
│   └── workflows/
│       ├── ci.yml                  # Lint + type-check on every PR
│       ├── eas-build.yml           # EAS Android preview on mobile changes
│       ├── railway-deploy.yml      # Railway deploy on backend/main merge
│       └── aws-amplify-deploy.yml  # Manual Amplify trigger (workflow_dispatch)
│
├── docker-compose.yml              # Local dev — FastAPI + Redis
├── .gitattributes                  # LF line endings
└── README.md
```

---

## Local Development

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | 20+ | [nodejs.org](https://nodejs.org) |
| Python | 3.11+ | [python.org](https://python.org) |
| Docker Desktop | Latest | [docker.com](https://docker.com) |
| EAS CLI | Latest | `npm install -g eas-cli` |
| Supabase account | — | [supabase.com](https://supabase.com) |

### 1 — Clone

```bash
git clone https://github.com/timothylee58/bayarlah.git
cd bayarlah
```

### 2 — Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — fill SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_ANON_KEY

# Start Redis via Docker
docker compose up -d redis

# Start FastAPI
uvicorn app.main:app --reload --port 8000
# API docs → http://localhost:8000/docs
```

### 3 — Database

Run both migration files in your Supabase project's SQL Editor, in order:

```sql
-- 1. Initial schema (bills, participants, payments, game_results, RLS)
-- File: supabase/migrations/20260531000001_initial_schema.sql

-- 2. Push tokens
-- File: supabase/migrations/20260531000002_push_tokens.sql
```

### 4 — Web Share Page

```bash
cd web
npm install
cp .env.example .env.local
# Edit .env.local — fill Supabase creds + NEXT_PUBLIC_API_URL

npm run dev
# → http://localhost:3000
```

### 5 — Mobile App

```bash
cd mobile
npm install

# Edit app.json → extra block:
#   supabaseUrl     → your Supabase project URL
#   supabaseAnonKey → your Supabase anon key
#   apiUrl          → http://localhost:8000
#   webUrl          → http://localhost:3000

npx expo start
# Scan QR with Expo Go (iOS/Android)
```

> **Push notifications** require a physical device and a built app (not Expo Go).
> Use `eas build --profile preview` for a testable APK.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `ENV` | Yes | `development` or `production` |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Service role key (bypasses RLS) |
| `SUPABASE_ANON_KEY` | Yes | Anon key (public operations) |
| `REDIS_URL` | Yes | Redis connection string |
| `CORS_ORIGINS` | Yes | JSON array of allowed origins |
| `JWT_SECRET` | Yes | Secret for JWT signing |

### Web (`web/.env.local`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase anon key |
| `NEXT_PUBLIC_API_URL` | Yes | FastAPI base URL |

### Mobile (`mobile/app.json` → `extra`)

| Key | Description |
|-----|-------------|
| `supabaseUrl` | Supabase project URL |
| `supabaseAnonKey` | Supabase anon key |
| `apiUrl` | FastAPI base URL |
| `webUrl` | Web share page base URL |

---

## Database Setup

### Schema Overview

```sql
-- bills: core entity
bills (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title         text NOT NULL,
  emoji         text,
  total_amount  numeric(10,2) NOT NULL,
  split_mode    text NOT NULL,   -- 'equal' | 'tangga' | 'roulette'
  organiser_id  uuid,            -- Supabase Auth user
  due_date      timestamptz,
  created_at    timestamptz DEFAULT now()
)

-- participants: bill members (no auth required)
participants (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bill_id       uuid REFERENCES bills ON DELETE CASCADE,
  name          text NOT NULL,
  amount_owed   numeric(10,2),
  share_token   text UNIQUE,     -- used in /pay/[billId]?token=...
  push_token    text
)

-- payments: append-only payment records
payments (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bill_id         uuid REFERENCES bills,
  participant_id  uuid REFERENCES participants,
  amount          numeric(10,2),
  method          text,           -- 'cash' | 'duitnow' | 'tng' | etc.
  confirmed_at    timestamptz DEFAULT now()
)

-- game_results: locked game outcomes
game_results (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bill_id     uuid REFERENCES bills,
  game_type   text,              -- 'tangga' | 'roulette'
  seed        integer,
  result      jsonb,
  created_at  timestamptz DEFAULT now()
)

-- push_tokens: Expo push tokens per participant/user
push_tokens (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_id  uuid,
  user_id         uuid,
  token           text NOT NULL,
  created_at      timestamptz DEFAULT now()
)
```

### RLS Policies Summary

| Table | Read | Write |
|-------|------|-------|
| `bills` | Organiser (JWT) + participant (share token) | Organiser only |
| `participants` | Organiser + self (share token) | Organiser only |
| `payments` | Organiser | Participant (share token) |
| `game_results` | Organiser + participants | Organiser only |
| `push_tokens` | Owning `user_id` only | Self only |

---

## Deployment

### Backend → Railway

Deploys automatically on push to `main` via `railway-deploy.yml` (triggers only on `backend/**` changes).

**Manual deploy:**
```bash
railway login
railway link
railway up --service bayarlah-backend
```

**Required Railway environment variables:**
```
ENV=production
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_ANON_KEY=your-anon-key
REDIS_URL=redis://default:password@your-redis.railway.internal:6379
CORS_ORIGINS=["https://your-service.awsapprunner.com"]
JWT_SECRET=your-secure-jwt-secret
```

Railway uses `backend/nixpacks.toml` for build detection and `backend/railway.toml` for service config (health check path, restart policy).

---

### Web → AWS App Runner (via ECR)

`web/next.config.ts` has `output: 'standalone'` enabled. The `web/Dockerfile` is a multi-stage build optimised for the standalone output.

**Step 1 — Build and push image:**
```bash
cd web

# Create ECR repository (one-time)
aws ecr create-repository \
  --repository-name bayarlah-web \
  --region ap-southeast-1

# Authenticate Docker to ECR
aws ecr get-login-password --region ap-southeast-1 \
  | docker login --username AWS --password-stdin \
    <account-id>.dkr.ecr.ap-southeast-1.amazonaws.com

# Build (env vars baked in at build time for Next.js NEXT_PUBLIC_* vars)
docker build \
  --build-arg NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co \
  --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key \
  --build-arg NEXT_PUBLIC_API_URL=https://your-backend.railway.app \
  -t bayarlah-web .

# Tag and push
docker tag bayarlah-web:latest \
  <account-id>.dkr.ecr.ap-southeast-1.amazonaws.com/bayarlah-web:latest
docker push \
  <account-id>.dkr.ecr.ap-southeast-1.amazonaws.com/bayarlah-web:latest
```

**Step 2 — Create App Runner service:**

1. AWS Console → App Runner → **Create service**
2. Source: **Container registry** → Amazon ECR → `bayarlah-web:latest`
3. Port: `3000`
4. CPU: 0.25 vCPU / Memory: 0.5 GB
5. Auto-deploy: enable (redeploys on new ECR push automatically)

**Step 3 — Update backend CORS:**
```
CORS_ORIGINS=["https://your-service-id.ap-southeast-1.awsapprunner.com"]
```

---

### Mobile → EAS Build

```bash
cd mobile

# One-time: link to EAS project
eas init
# Copy the generated project ID into mobile/app.json → extra.eas.projectId

# Preview APK (sideloadable on Android — good for testing)
eas build --platform android --profile preview

# Production build
eas build --platform android --profile production
eas build --platform ios --profile production

# OTA update (JS-only changes — no store review needed)
eas update --channel production --message "Fix nudge cooldown display"
```

**EAS build profiles** (`mobile/eas.json`):

| Profile | API URL | Distribution |
|---------|---------|--------------|
| `development` | `localhost:8000` | Internal (dev client) |
| `preview` | Railway backend | Internal APK |
| `production` | Railway backend | Store (Play / App Store) |

---

## API Reference

Base URL: `https://your-backend.railway.app`

### Bills

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/bills` | JWT | Create bill with participants |
| `GET` | `/api/bills` | JWT | List organiser's bills |
| `GET` | `/api/bills/{id}` | Share token | Fetch bill (share page) |
| `DELETE` | `/api/bills/{id}` | JWT | Delete bill |

### Payments

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/payments/{bill_id}/confirm` | Share token | Confirm participant payment |
| `POST` | `/api/payments/{bill_id}/nudge/{participant_id}` | JWT | Send WhatsApp nudge (24h rate limit via Redis) |

### Game

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/game/{bill_id}/tangga/generate` | JWT | Generate seeded ladder, return rungs + seed |
| `POST` | `/api/game/{bill_id}/tangga/lock` | JWT | Commit Tangga result to DB + Redis |
| `POST` | `/api/game/{bill_id}/roulette/spin` | JWT | Compute winner + velocity before animation |
| `POST` | `/api/game/{bill_id}/roulette/lock` | JWT | Commit Roulette result to DB + Redis |

### WebSocket

```
WS /ws/dashboard/{bill_id}?token={jwt_or_share_token}
```

- Sends `init` on connect (full bill state)
- Broadcasts `payment_confirmed` to all connections for the bill on every payment
- Server pings every 30s; client must respond with `pong` or connection is dropped

### Notifications

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/notifications/register` | JWT / Share token | Upsert Expo push token |
| `DELETE` | `/api/notifications/unregister/{id}` | JWT | Remove push token |

---

## Game Algorithms

### Tangga — Seeded Ladder Generation

```
1. Server: generate random integer seed
2. Server: create random.Random(seed) — Python stdlib seeded PRNG
3. For each row (top → bottom):
   - With p=0.4, attempt to place a horizontal rung
   - Rung connects adjacent lanes
   - Constraint: no two rungs share a lane in the same row
4. Seed + rung grid sent to client in generate response
5. Client: recreate identical grid using mulberry32(seed)
   - Same sequence of calls → same rung placement
6. Path traversal: start at chosen lane, descend row by row,
   follow any rung encountered left or right
7. Result (payer assignment) committed to Supabase + Redis atomically
```

**mulberry32 — TypeScript PRNG matching Python random:**
```typescript
function mulberry32(seed: number) {
  return function (): number {
    seed |= 0;
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
```

### Pusing — Roulette Physics

```
1. Server: compute winning segment index (random.randint)
2. Server: calculate exact stop angle:
     angle = full_spins * 360 + segment_midpoint_degrees
     full_spins = random.randint(5, 8)  — enough to look convincing
3. Server: randomise spin duration (4000–6000ms) for visual variety
4. Client: animate wheel to computed angle using:
     cubic-bezier(0.17, 0.67, 0.12, 0.99)  — fast start, slow decelerate
5. Winner committed to DB *before* animation starts — cannot be manipulated
6. Confetti fires on animation end via runOnJS callback
```

**SVG arc path per wheel segment:**
```typescript
function slicePath(
  cx: number, cy: number, r: number,
  startAngle: number, endAngle: number
): string {
  const x1 = cx + r * Math.cos(startAngle);
  const y1 = cy + r * Math.sin(startAngle);
  const x2 = cx + r * Math.cos(endAngle);
  const y2 = cy + r * Math.sin(endAngle);
  const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
  return `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;
}
```

---

## Design System

### Colours

| Token | Hex | Usage |
|-------|-----|-------|
| Brand Red | `#C8410A` | CTAs, loser reveals, "Kena kau lah" banner |
| Turmeric Gold | `#BA7517` | Nudge buttons, mid-progress states |
| Forest Green | `#1D9E75` | Paid states, success confirmations |
| Dark BG | `#0F0D0B` | Dark mode background |
| Light BG | `#FAFAF8` | Light mode background |
| Surface Dark | `#1A1612` | Cards on dark background |
| Muted Text | `#6B6560` | Secondary labels |

### Motion

| Context | Easing | Duration |
|---------|--------|----------|
| Tangga path traversal | `ease-in-out` | 600ms per segment |
| Pusing wheel spin | `cubic-bezier(0.17, 0.67, 0.12, 0.99)` | 4000–6000ms |
| Progress ring pop | `spring(damping: 15, stiffness: 180)` | Native driver |
| Confetti particles | `withTiming` | 3500ms lifetime |
| Toast appear | `withSpring` | 300ms |

### Bill Emoji Tags

`🍜` `🛒` `🏠` `✈️` `🎉` `🎮` `📚` `💊` `🚗` `⚽`

### Payment Methods

DuitNow QR · Touch 'n Go · Cash · Bank Transfer · Others

---

## CI/CD Pipeline

### Triggers

```
Every PR / push to any branch:
  ci.yml → lint + type-check (backend + web)

Merge to main (backend/** changed):
  railway-deploy.yml → Railway deploy

Merge to main (mobile/** changed):
  eas-build.yml → EAS Android preview build

Manual (workflow_dispatch):
  aws-amplify-deploy.yml → Amplify redeploy
```

### `ci.yml` steps

```yaml
backend:
  - ruff check backend/         # Python linting
  - pytest backend/tests/ -q    # Unit tests

web:
  - npm run lint                 # ESLint
  - npx tsc --noEmit             # TypeScript type check
```

### Required GitHub Secrets

| Secret | Workflow |
|--------|----------|
| `RAILWAY_TOKEN` | `railway-deploy.yml` |
| `EXPO_TOKEN` | `eas-build.yml` |
| `AWS_ACCESS_KEY_ID` | `aws-amplify-deploy.yml` |
| `AWS_SECRET_ACCESS_KEY` | `aws-amplify-deploy.yml` |
| `AWS_REGION` | `aws-amplify-deploy.yml` |
| `AWS_AMPLIFY_APP_ID` | `aws-amplify-deploy.yml` |

---

## Portfolio Notes

Built to demonstrate to **Malaysian / Singapore tech employers:**

| Skill demonstrated | Evidence in codebase |
|-------------------|----------------------|
| Real-time multiplayer UX | `ws_manager.py` singleton; Supabase Realtime on share page; live progress ring with zero polling |
| Gamification engineering | Seeded deterministic RNG (mulberry32 ↔ Python random), path traversal, physics-based deceleration |
| Mobile-first React Native | Expo Router, Reanimated 3 native-driver animations, SVG roulette wheel, Expo Push, deep-link handling |
| Production FastAPI | Async routes, Pydantic v2, Redis game state locking, Supabase RLS |
| Cloud deployment | Railway (nixpacks auto-detect), AWS App Runner (ECR), EAS Build (Android + iOS), OTA updates |
| CI/CD discipline | Per-service GitHub Actions workflows, type-check gate on every PR |
| Malaysian product thinking | MYR currency, Bahasa Malaysia copy, WhatsApp nudge deeplinks, hawker / housemate culture context |

---

*Bayar.lah — Timothy Lee · June 2026 · [github.com/timothylee58](https://github.com/timothylee58)*
