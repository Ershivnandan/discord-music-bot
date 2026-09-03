"""Monkey-patch for discord.py's audio player thread."""

import time

import discord
from discord.enums import SpeakingState


def patch_audio_player():
    """Stop discord.py's fast-forward bursts after a stall.

    The stock AudioPlayer._do_run schedules packet N at start + N*20ms. If the
    thread stalls (CPU starvation on Render's 0.1-CPU instance), every packet
    afterwards is "late", so it sends them back-to-back to catch up — heard as
    a few seconds of 2x-speed audio. This copy of the loop (discord.py 2.7.1)
    resyncs the clock after a big stall instead, trading the burst for a brief
    gap, which sounds far less jarring.
    """
    max_lag = 0.2  # seconds behind schedule before we resync instead of burst

    def _do_run(self):
        self.loops = 0
        self._start = time.perf_counter()

        client = self.client
        play_audio = client.send_audio_packet
        self._speak(SpeakingState.voice)

        while not self._end.is_set():
            if not self._resumed.is_set():
                self.send_silence()
                self._resumed.wait()
                continue

            data = self.source.read()

            if not data:
                if self._current_error is None:
                    source_error = getattr(self.source, "_current_error", None)
                    if source_error:
                        self._current_error = source_error
                self.stop()
                break

            if not client.is_connected():
                connected = client.wait_until_connected(client.timeout)
                if self._end.is_set() or not connected:
                    return
                self._speak(SpeakingState.voice)
                self.loops = 0
                self._start = time.perf_counter()

            play_audio(data, encode=not self.source.is_opus())
            self.loops += 1
            next_time = self._start + self.DELAY * self.loops
            now = time.perf_counter()
            if now - next_time > max_lag:
                # fell way behind schedule: drop the backlog, don't burst it
                self._start += now - next_time
                next_time = now
            delay = max(0, self.DELAY + (next_time - now))
            time.sleep(delay)

        if client.is_connected():
            self.send_silence()

    discord.player.AudioPlayer._do_run = _do_run
