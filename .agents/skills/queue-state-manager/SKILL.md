---
name: queue-state-manager
description: >-
  Use this skill when managing per-guild playback states, playlist manipulation (shuffle,
  loop/repeat, history, remove, move), concurrency and generation counters, or voice channel
  inactivity auto-disconnects.
---

# Queue & State Manager Skill

This skill governs guild-specific audio playback states, playlist collections, and asynchronous race-condition prevention.

## Guild Player State Model

Each Discord server (guild) has its own isolated `GuildPlayer` instance managed in `PlaybackManager.players` dictionary:

```python
class GuildPlayer:
    def __init__(self):
        self.playlist = []       # list of (title, file_path) tuples
        self.index = -1          # current playing position index
        self.speed = 1           # current playback speed multiplier (1, 2, 3)
        self.generation = 0      # generation token for concurrency safety
        self.message = None      # discord.Message reference for the player card
        self.ctx = None          # last command Context for invoking actions
```

## The Generation Counter Protocol

### Why It Exists
When a song finishes naturally, discord.py's audio worker thread executes the `after` callback:
```python
def after_playing(error):
    # This callback runs when FFmpeg terminates
```
However, if a user clicks `!next`, `!prev`, or changes `!speed` *before* the song ends, `voice.stop()` or `voice.play()` terminates the current stream. This also triggers the `after_playing` callback of the previous track! Without a guard, the callback would auto-advance, triggering a double skip.

### The Fix
1. Whenever playback is manually started, stopped, or speed-adjusted, bump `player.generation += 1`.
2. Capture `generation = player.generation` in a local variable before passing `after_playing` to `voice.play()`.
3. Inside `after_playing(error)`:
   ```python
   if generation != player.generation:
       return  # superseded by manual restart or skip
   asyncio.run_coroutine_threadsafe(self.advance(ctx), self.bot.loop)
   ```

## Adding Queue Features Safely

### 1. Loop / Repeat Mode
- **Repeat Off**: Advance index monotonically (`player.index + 1`). If `>= len(playlist)`, go idle.
- **Repeat Track**: Replay current index `player.play_index(ctx, player.index)`.
- **Repeat Queue**: If `player.index + 1 >= len(playlist)`, wrap around to index `0`.

### 2. Shuffle
- To preserve playback history, shuffle only the unplayed portion of the playlist (`player.playlist[player.index + 1:]`), leaving previous songs in order for `!prev`.

### 3. Voice Inactivity Auto-Disconnect
- Track voice channel member counts in `on_voice_state_update`.
- If the bot is the only member remaining in the voice channel, start an inactivity timer (e.g. 180 seconds). Cancel the timer if a user rejoins; call `disconnect_and_cleanup()` if the timer expires.
