# 🏭 NEXA Factory — Telegram Bot Factory

> **Run dozens of Telegram bots from a single engine** — create, manage, and broadcast across your entire bot fleet from one Arabic control panel. Zero external dependencies, Termux-ready.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot_API-2CA5E0.svg)](https://core.telegram.org/bots/api)
[![Dependencies](https://img.shields.io/badge/Dependencies-Zero-brightgreen.svg)](#-tech-stack)
[![Platform](https://img.shields.io/badge/Platform-Termux%20%7C%20Android-3DDC84.svg)](https://termux.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📖 About

**NEXA Factory** is a "bot factory" engine that runs on Termux/Android. Instead of deploying each Telegram bot separately, you run **one engine** that hosts them all.

How it works: you talk to the **main factory bot**, tap **"صنع بوت جديد"** (Create New Bot), send the token you got from [@BotFather](https://t.me/BotFather) — and your new bot is **live instantly**, managed from the same place.

---

## ✨ Key Features

### 🤖 Multi-Bot Engine
- **Synchronous polling engine** hosting up to ~200 bots simultaneously
- **Per-bot offset tracking** — each bot resumes exactly where it left off
- **Error recovery** with a supervisor poller that restarts failed workers
- **~30 messages/second** rate limit per bot with automatic handling of Telegram `429` errors

### 📬 Priority Task Queue
- **HIGH priority** for user messages (instant responses)
- **LOW priority** for broadcasts and backups (never blocks chat)
- Smart scheduling so heavy jobs never slow down conversations

### 💬 Per-Bot Message Handlers
- Custom **commands** per bot
- **Auto-replies** triggered by keywords
- **Forced channel subscription** — require users to join your channel first
- **User banning** and **message forwarding** rules

### 📢 Mass Broadcasting
- **Streaming broadcast engine** — send to thousands of users without memory spikes
- **Scheduled broadcasts** for campaigns and announcements
- **Compressed CSV export/backup** of user data

### 🎛️ Arabic Control Panels
- **Factory bot** (`factory_bot.py`) — fully Arabic interface to create and manage bots
- **Per-bot admin panels** — change name, photo, commands, and settings for each bot individually

---

## 🛠️ Tech Stack

| Component      | Technology                                                        |
|----------------|-------------------------------------------------------------------|
| Language       | Python 3.11+ (`asyncio`)                                          |
| Dependencies   | **Zero — standard library only, by design**                       |
| HTTP           | `urllib.request` (instead of `httpx`)                             |
| Database       | `sqlite3` with WAL mode → `data/factory.db` (instead of aiosqlite) |
| Excel/Export   | `csv` + `zipfile` (instead of `openpyxl`)                         |
| Config         | Hand-rolled `.env` parser (instead of `python-dotenv`)            |

> 📱 **Why zero dependencies?** The engine is designed for **Termux on Android**, where compiling native packages is painful. Everything runs on the Python standard library — nothing to install, nothing to break.

---

## 🚀 Installation

### Prerequisites
- Python 3.11+
- A Telegram bot token for the factory bot from [@BotFather](https://t.me/BotFather)

### Setup (Termux / Linux)

```bash
# 1. Clone the repository
git clone https://github.com/tahagamer712-beep/Factory-bot.git
cd Factory-bot

# 2. Copy files to the working directory
mkdir -p ~/factory && cp -r . ~/factory/ && cd ~/factory

# 3. (Optional) Run the installer — installs nothing by design
bash install.sh
# or: pip install -r requirements-termux.txt  # intentionally empty

# 4. Configure environment
cp .env.example .env
# Edit .env and fill in:
#   FACTORY_BOT_TOKEN=your_factory_bot_token
#   ADMIN_ID=your_telegram_user_id

# 5. Run the factory
python main.py
```

### Creating Your First Bot
1. Open your factory bot on Telegram
2. Tap **"صنع بوت جديد"** (Create New Bot)
3. Send the token from [@BotFather](https://t.me/BotFather)
4. ✅ Your new bot is live immediately!

---

## ⚙️ Configuration

| Variable            | Required | Description                              |
|---------------------|----------|------------------------------------------|
| `FACTORY_BOT_TOKEN` | ✅       | Token of the main factory bot            |
| `ADMIN_ID`          | ✅       | Telegram user ID of the factory admin    |

See `.env.example` for the full list.

---

## 📁 Project Structure

```
Factory-bot/
├── main.py               # Entry point — starts the engine
├── factory_bot.py        # Main factory bot (Arabic UI)
├── engine/
│   ├── poller.py         # Multi-bot polling engine + supervisor
│   ├── queue.py          # Priority task queue
│   ├── broadcaster.py    # Streaming broadcast engine
│   └── rate_limiter.py   # Per-bot rate limiting (429 handling)
├── handlers/
│   ├── commands.py       # Per-bot commands
│   ├── autoreply.py      # Keyword auto-replies
│   └── subscription.py   # Forced channel subscription
├── data/
│   └── factory.db        # SQLite database (WAL mode)
├── install.sh            # Termux installer
├── .env.example          # Environment template
└── requirements-termux.txt  # Intentionally empty (stdlib only)
```

---

## 💡 Usage Examples

**Broadcast to all users of one bot:**
> Factory Panel → Select Bot → Broadcast → Send your message → Done. Delivered in a memory-efficient stream.

**Add a keyword auto-reply:**
> Bot Admin Panel → Auto-Replies → Add Keyword → Set the reply text.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 📬 Contact

- **Developer:** [@tahagamer712-beep](https://github.com/tahagamer712-beep)
- **Issues:** [GitHub Issues](https://github.com/tahagamer712-beep/Factory-bot/issues)

---

<p align="center">One engine. Unlimited bots. 🚀</p>
