# 🏭 NEXA Factory — Multi-Bot Telegram Engine

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Telegram-Bot%20API-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram">
  <img src="https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
  <img src="https://img.shields.io/badge/Termux-Ready-000000?style=for-the-badge&logo=android&logoColor=white" alt="Termux">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
</p>

<p align="center">
  <b>Create, host and manage unlimited Telegram bots from a single engine.</b><br>
  Users build their own bots through a factory bot — every bot ships with a
  professional, full-featured admin panel out of the box.
</p>

---

## ✨ What is this?

**NEXA Factory** is a Telegram bot factory: one engine that hosts many bots at once.
A user talks to the **factory bot**, registers their own bot token (from [@BotFather](https://t.me/BotFather)),
and instantly gets a working bot with:

- 📨 Anonymous message relay with smart owner notifications
- 🎛️ A complete admin panel (no code needed)
- 📊 Real analytics, health monitoring and alerts
- 💾 Backup / restore with integrity verification
- 🔐 Granular staff permissions + immutable audit log

Everything runs on **pure async Python** — no heavy Telegram frameworks, no servers to pay for.
It was built to run 24/7 on a phone via Termux, but works anywhere Python runs.

---

## 🚀 Feature Highlights

### 🤖 For bot owners (created bots)

| Area | What's inside |
|---|---|
| **Command Center** | Live user stats, recent admin events — all numbers from real DB queries |
| **User Management** | Search by ID/username, profiles, internal notes, block/unblock, action history |
| **Reports & Safety** | Report queue (new / in-review / closed), moderator decisions: dismiss / warn / ban |
| **Broadcast** | Preview before sending, test on your own account, double-run protection, job tracking with resume |
| **Analytics** | New users (day / 7d / 30d), active users, acquisition trends, peak hours, report resolution time — Baghdad timezone |
| **Health & Alerts** | Polling status, DB integrity, stuck-operation detection, alert lifecycle (new → ack → resolved) |
| **Backup Center** | Full-DB backups, `integrity_check` verification, isolated restore drills |
| **Staff & Permissions** | 10 granular permissions, role templates, backend-enforced checks, owner always supreme |
| **Audit Log** | Append-only record of every sensitive action — tokens auto-redacted, never deletable from UI |
| **Maintenance Mode** | Toggle with custom message — owner panel stays reachable |

### 🏭 For the factory itself

- Token-based bot registration with live `getMe` validation
- Per-bot profile management (name, bio, description, photo, commands) via Bot API
- Startup token guard — invalid tokens are skipped with a warning instead of retrying forever
- 13-section factory admin panel (bots, owners, stats, broadcasts, bans, backups, DB, settings, system, logs, moderators…)

### ⚙️ Engine internals

- Async long-polling supervisor — one event loop, unlimited bots concurrently
- Priority job queue with retries, backoff, and crash-resume
- Per-bot rate limiting with Telegram 429 handling
- SQLite with WAL, transactions, and non-destructive migrations
- Connection pooling, no blocking calls in the hot path

---

## 🏗️ Architecture

```
                    🏭 NEXA Factory
                          │
     ┌────────────────────┼────────────────────┐
     │                    │                    │
 📱 Telegram           🗄️ SQLite            ⚙️ Workers
     │                    │                    │
  Updates              Database            Processing
     │
 TelegramAdapter (pure httpx, async)
     ├─ long polling (30s timeout)
     ├─ send / edit / copy messages
     └─ Bot API management calls
```

Each registered bot gets its own poller task under one supervisor.
Admin panels are generated per bot from a shared, reusable template.

---

## 📁 Project Structure

```
Factory-bot/
├── main.py                 # Entry point — loads bots, starts pollers & workers
├── factory_bot.py          # The factory bot (user-facing: create/manage bots)
├── dispatcher.py           # Update routing (messages, callbacks, verification)
├── telegram_adapter.py     # Pure-httpx Bot API client + connection pool
├── message_sender.py       # Rate-limited sending with 429 retry
├── forwarding.py           # User→admin message relay + reply-mode
├── broadcast_engine.py     # Job-based broadcasts with resume & progress
├── poller.py               # Per-bot long pollers + supervisor
├── db.py                   # SQLite layer (migrations, stats, audit, backups)
├── backup.py               # Backup creation / verification / restore
├── bot_registry.py         # In-memory registry of hosted bots
├── admin_panel/            # Reusable admin panel (screens, keyboards, router,
│                           #   flows, permissions, audit, health, stats)
├── factory_admin/          # The factory's own 13-section admin panel
├── verification.py         # Membership-gate / force-subscribe logic
├── requirements-termux.txt  # Dependencies
└── test_phase*.py           # Test suites (run all before every release)
```

---

## 📱 Installation (Termux)

```bash
# 1. Clone
git clone https://github.com/tahagamer712-beep/Factory-bot.git
cd Factory-bot

# 2. Install dependencies
pip install -r requirements-termux.txt

# 3. Configure
cp .env.example .env
# then edit .env with your FACTORY_BOT_TOKEN and ADMIN_ID
nano .env

# 4. Run (recommended: inside tmux for 24/7)
python main.py
```

> 💡 Keep it alive: `tmux new -s bots` → run → detach with `Ctrl-b d`.

### 🖥️ Any other machine

Same steps — Python 3.11+, pip, and a `.env`. No Termux-specific code paths.

---

## ⚙️ Configuration

Copy `.env.example` → `.env`:

```env
FACTORY_BOT_TOKEN=your_factory_bot_token_here   # from @BotFather
ADMIN_ID=your_telegram_user_id                  # factory owner

# Optional tuning (sane defaults built in)
LOG_LEVEL=INFO
MAX_WORKERS=4
LONG_POLL_TIMEOUT=30
```

> 🔒 `.env` is git-ignored. **Never commit tokens.** The `.env.example` is the documented template.

---

## 🧪 Testing

```bash
python test_phase1.py        # core engine
python test_phase2.py        # messaging & forwarding
python test_phase3.py        # broadcast & jobs
python test_phase4.py        # admin panel
python test_phase5_6.py      # backup & misc
python test_security_fixes.py
python test_phase2_admin.py   # permissions, audit, backup (36 tests)
python test_phase3_admin.py   # analytics, health, alerts (50 tests)
```

Every feature ships only after live verification against real Telegram —
no mocks presented as proof.

---

## 🗺️ Roadmap

- [x] Multi-bot async engine
- [x] Factory bot with token registration
- [x] Professional admin panel (3 phases)
- [x] Analytics, health monitoring & alerts
- [x] Backup / restore with verification
- [x] Granular permissions + audit log
- [ ] Growth metrics & referral system
- [ ] Guided BotFather onboarding wizard

---

## 🤝 Contributing

Pull requests are welcome. Please:

1. Audit the code/DB before changing behavior — every screen must be wired to a real function.
2. Never add fake buttons or placeholder numbers.
3. Back up before migrations; keep them non-destructive.
4. Run the full test suite before submitting.

---

## 📄 License

MIT — do whatever you want, just don't blame us. See [LICENSE](LICENSE).

---

<p align="center">
  Built with ☕ and stubbornness — running 24/7 on a phone in Baghdad 🇮🇶
</p>
