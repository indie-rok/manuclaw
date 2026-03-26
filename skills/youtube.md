# YouTube Skill

## Handling edge cases
- Shortened URLs (youtu.be/ID) are valid — extract the ID from the path
- Playlist URLs contain both list= and v= params — use v= for the video ID
- YouTube Shorts URLs (/shorts/ID) — the ID is in the path
- Some videos have auto-generated transcripts (prefixed with "a.") — try those as fallback

## Language fallbacks
Try languages in this order: en, en-US, a.en (auto-generated), fr, fr-FR, a.fr
If all fail, report which languages are available.

## Transcript tips
- Transcripts can be very long (10k+ words). Always summarize before presenting.
- Auto-generated transcripts have no punctuation — the summarizer handles this fine.
