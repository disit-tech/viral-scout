"""Video generation for a business profile: recording + script → captioned 1080×1920 master, cards, voice clone,
stills and HyperFrames films.

  python -m viral_scout video doctor
  python -m viral_scout video <profile> cut|make|render|cards|voice|film|still|info ...

Everything brand-specific comes from the profile's `studio:` and `video:` blocks (see docs/video.md).
Heavy tools are optional and live outside the main install: WhisperX in `.venv-video`, Chatterbox in `.venv-voice`,
Playwright and HyperFrames in `viral_scout/video/node/node_modules`. Nothing here imports them at module level.
"""
