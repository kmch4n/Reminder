# Reminder Bot

A LINE reminder bot that allows users to schedule reminders via natural language messages.

## Features

- **Natural language time parsing**: Supports 13+ Japanese time patterns (e.g., "10分後", "明日9時", "毎週月曜 20時")
- **Interactive registration flow**: Conversational interface with QuickReply buttons
- **Multiple schedule types**:
  - One-time reminders (specific date and time)
  - Weekly recurring reminders (specific day of week)
  - Monthly recurring reminders (specific day of month)
- **Archive system**: Completed reminders are automatically moved to archive.json
- **Adaptive scheduling**: Scheduler adjusts sleep interval based on next reminder
- **JSON-based storage**: Simple file-based persistence without database dependencies
- **Self-hosted**: Runs on your own Ubuntu server

## Architecture

The bot consists of two main components:

- **receive.py**: Flask webhook server that receives LINE messages and manages interactive reminder registration
- **send.py**: Scheduler daemon that checks for due reminders and sends push messages with adaptive sleep intervals

## Requirements

- Python 3.10+
- LINE Messaging API account (Channel Access Token and Channel Secret)
- Ubuntu server (or similar Linux environment)
- Public HTTPS endpoint for LINE webhook

## Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd Reminder
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env and add your LINE credentials
   ```

4. Create data directory:
   ```bash
   mkdir -p data
   ```

## Configuration

Set the following environment variables in `.env`:

- `LINE_CHANNEL_ACCESS_TOKEN`: Your LINE channel access token
- `LINE_CHANNEL_SECRET`: Your LINE channel secret
- `REMINDER_PUBLIC_URL` (optional): Public webhook URL for display (default: `https://your-domain.com/reminder/callback`)
- `REMINDER_DATA_DIR` (optional): Data directory path (default: `./data`)
- `REMINDER_TIMEZONE` (optional): Timezone (default: `Asia/Tokyo`)

## Usage

### Running the Webhook Server

Start the Flask server to receive LINE webhook events:

```bash
python receive.py
```

The server will listen on port 8000 by default. Configure your LINE webhook URL to point to `https://your-domain.com/reminder/callback`.

### Running the Scheduler

Start the scheduler to process and send due reminders:

```bash
python send.py
```

For production, consider running `send.py` as a systemd service or via cron.

### Using the Bot

Users interact with the bot through LINE messages:

#### Setting up a new reminder

1. Send "リマインド設定" or directly send the reminder content
2. The bot asks for the time
3. Send the time in natural language
4. Reminder is registered

#### Natural language time examples

**Relative time**:
- `10分後` (in 10 minutes)
- `2時間後` (in 2 hours)
- `3日後` (in 3 days)

**Absolute time**:
- `22:00` (today at 22:00, or tomorrow if already passed)
- `14時` (today at 14:00, or tomorrow if already passed)
- `午後3時` (today at 3:00 PM, or tomorrow if already passed)

**Date + time**:
- `今日の22:00` (today at 22:00)
- `明日 9時` (tomorrow at 9:00)
- `明後日 午後3時` (day after tomorrow at 3:00 PM)
- `2025年5月3日 14:00` (specific date and time)
- `11/20` (November 20th at 9:00 AM)

**Recurring reminders**:
- `毎週日曜日 20時` (every Sunday at 20:00)
- `毎月1日 20時` (1st of every month at 20:00)

#### Viewing reminders

Send "リマインド一覧" to see all pending reminders.

#### QuickReply buttons

All bot responses include QuickReply buttons for easy navigation:
- **リマインド設定**: Start setting up a new reminder
- **リマインド一覧**: View all pending reminders

## Data Storage

Reminders are stored in JSON files:

- **data/reminders.json**: Active pending reminders
- **data/archive.json**: Completed reminders with `archived_at` timestamp

Each reminder object contains:

- `id`: Unique identifier (UUID)
- `user_id`: LINE user ID
- `text`: Reminder message
- `schedule`: Schedule configuration (type, datetime, recurrence pattern)
- `next_run_at`: Next execution time (ISO 8601 format with timezone)
- `created_at`: Creation timestamp
- `status`: Current status (`pending`, `done`)

Completed reminders include an additional `archived_at` field when moved to archive.

## Development

### Project Structure

```
Reminder/
├── receive.py          # Flask webhook server
├── send.py             # Scheduler daemon
├── storage.py          # JSON file operations
├── time_parser.py      # Natural language time parsing
├── session.py          # User session management
├── helpers.py          # Reminder creation and display utilities
├── data/
│   ├── reminders.json  # Active reminders
│   └── archive.json    # Completed reminders
├── .env.example        # Environment variables template
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

### Key Components

**Natural Language Time Parser** (`time_parser.py`):
- Supports 13+ Japanese time patterns
- Handles relative time (分後, 時間後, 日後)
- Handles absolute time with 午前/午後 modifiers
- Handles recurring schedules (毎週, 毎月)
- Automatic past time detection and adjustment

**Interactive Session Management** (`session.py`):
- In-memory session storage for conversational flow
- Fail counter with automatic session clearing after 5 failed attempts
- Cancel command support

**Scheduler** (`send.py`):
- Adaptive sleep interval (adjusts based on next reminder, max 30s)
- 60-second grace period (overdue reminders are archived without execution)
- Automatic archiving of completed reminders

### Coding Style

- Type hints throughout
- Black formatting
- Descriptive function and variable names
- Small, focused functions

## License

MIT License (or specify your preferred license)

## Contributing

Contributions are welcome! Please ensure your code:
- Uses type hints
- Follows Black formatting standards
- Includes clear, descriptive names
- Has focused, single-purpose functions
