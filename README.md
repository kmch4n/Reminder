# Reminder Bot

A LINE reminder bot that allows users to schedule reminders via LINE messages.

## Features

- **One-time reminders**: Schedule a reminder for a specific date and time
- **Weekly reminders**: Recurring reminders on specific days of the week
- **Monthly reminders**: Recurring reminders on specific days of the month
- **JSON-based storage**: Simple file-based persistence without database dependencies
- **Self-hosted**: Runs on your own Ubuntu server

## Architecture

The bot consists of two main components:

- **receive.py**: Flask webhook server that receives LINE messages and saves reminders
- **send.py**: Scheduler daemon that checks for due reminders and sends push messages

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
- `REMINDKUN_DATA_DIR` (optional): Data directory path (default: `./data`)
- `REMINDKUN_TIMEZONE` (optional): Timezone (default: `Asia/Tokyo`)

## Usage

### Running the Webhook Server

Start the Flask server to receive LINE webhook events:

```bash
python receive.py
```

The server will listen on port 8000 by default. Configure your LINE webhook URL to point to `https://your-domain.com/callback`.

### Running the Scheduler

Start the scheduler to process and send due reminders:

```bash
python send.py
```

For production, consider running `send.py` as a systemd service or via cron.

### Reminder Format Examples

Users can send messages to the LINE bot in the following formats:

- **One-time reminder**: `/once 2025-11-20 21:00 レポートをやる`
- **Weekly reminder**: `/weekly 月曜 09:00 ゴミ出し`
- **Monthly reminder**: `/monthly 2 21:00 家賃の支払い`

*Note: Natural language parsing support is planned for future releases.*

## Data Storage

Reminders are stored in `data/reminders.json` as a JSON array. Each reminder object contains:

- `id`: Unique identifier (UUID)
- `user_id`: LINE user ID
- `text`: Reminder message
- `schedule`: Schedule configuration (type, datetime, recurrence pattern)
- `next_run_at`: Next execution time (ISO 8601 format with timezone)
- `created_at`: Creation timestamp
- `status`: Current status (`pending`, `done`)

## Development

### Project Structure

```
Reminder/
├── receive.py          # Flask webhook server
├── send.py             # Scheduler daemon
├── data/
│   └── reminders.json  # JSON storage file
├── .env.example        # Environment variables template
├── requirements.txt    # Python dependencies
├── CLAUDE.md           # Development guidelines
└── README.md           # This file
```

### Coding Guidelines

See [CLAUDE.md](CLAUDE.md) for detailed development guidelines, including:

- Coding style and naming conventions
- Architecture decisions
- Commit message format
- Testing strategies

## License

MIT License (or specify your preferred license)

## Contributing

Contributions are welcome! Please ensure you follow the guidelines in CLAUDE.md.
