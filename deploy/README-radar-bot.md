# FOUR-LIFE Radar Bot

Broadcasts Certified tier transitions to X as soon as they fire.

## Install on the VPS

```bash
# On /opt/four-life (already has .env with TWITTER_* creds)
sudo cp deploy/radar-bot.service /etc/systemd/system/radar-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now radar-bot.service
sudo systemctl status radar-bot --no-pager
```

Logs: `journalctl -u radar-bot -f`

## Health

- `GET /api/radar-bot/status` returns running/last_tick/posts_last_hour.
- `data/radar_bot_state.json` holds per-token last-seen tier + dedup cache.

## Tuning

- Rate limit: 6 posts/hour (`MAX_POSTS_PER_HOUR` in `agent/social/radar_bot.py`).
- Tick interval: 5 min (`TICK_INTERVAL_SECONDS`).
- Error pause: 10 min (`ERROR_PAUSE_SECONDS`).

## What it posts

- Any token → `graduated` → 🎓 tweet with `@fourmeme_official` tag.
- First sighting at `graduation_watch` or upgrade from `healthy`/`observed` → ⚡ tweet.
- First sighting at `at_risk` or downgrade → 🚨 tweet with evidence summary.
- Upgrade to `healthy` → 🌱 tweet.

All templates are deterministic. No LLM involvement in the social alerts.
