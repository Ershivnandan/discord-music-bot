---
name: discord-ui-architect
description: >-
  Use this skill when designing or modifying Discord UI components, Player Card embeds,
  interactive buttons, select menus, modals, slash commands (app_commands), hybrid commands,
  or ephemeral interaction feedback.
---

# Discord UI Architect Skill

This skill guides the design and implementation of Discord interactive components, rich embeds, and application commands.

## Player Card Architecture

The player card is the central visual interface for users. It combines an Embed with an interactive `discord.ui.View`.

### Dynamic Message Re-anchoring
Chat messages in active channels quickly bury older bot responses. To ensure buttons remain accessible:
```python
async def refresh_player(self, ctx):
    player = self.get_player(ctx.guild.id)
    embed = build_embed(player, ctx.guild)
    view = PlayerView(self, ctx.guild.id)
    message = player.message
    channel = ctx.channel

    # If the card is already the latest message in the channel, edit it in place
    if message and message.channel.id == channel.id and channel.last_message_id == message.id:
        try:
            await message.edit(embed=embed, view=view)
            return
        except discord.HTTPException:
            pass
    
    # Otherwise delete and re-send at the very bottom
    if message:
        try:
            await message.delete()
        except discord.HTTPException:
            pass
    player.message = await channel.send(embed=embed, view=view)
```

### Component Guidelines
1. **Interactive Buttons (`discord.ui.Button`)**:
   - Always set `timeout=None` for persistent views that survive beyond a single interaction.
   - Defer immediately on state-changing button clicks: `await interaction.response.defer()` to avoid Discord's 3-second interaction timeout.
   - Use `custom_id` naming conventions (e.g. `speed_1`, `speed_2`, `prev`, `next`, `pause`, `stop`).
   - Dynamically toggle button styles (e.g., `discord.ButtonStyle.primary` for the active speed, `discord.ButtonStyle.secondary` for inactive speeds).
2. **Ephemeral Feedback**:
   - For user-specific errors (e.g. "You must be in a voice channel", "No previous song"), use `await interaction.response.send_message(..., ephemeral=True)` so server channels stay clean.

## Converting to Slash & Hybrid Commands

When transitioning prefix commands (`!play`) to modern Application Commands:
- Use `commands.hybrid_command` to maintain backwards compatibility with `!` prefix users while offering autocomplete slash command experiences (`/play`).
- Ensure `await bot.tree.sync()` is called carefully in `setup_hook` or a dedicated owner command to register application commands with Discord.
