# Step 4 — Voice Input (+ English-canonical typed text)

`POST /api/chat/message` accepts a voice note as well as typed text. Send `multipart/form-data`
with the usual fields plus an `audio` file (send `text` OR `audio`, never both). Gemini transcribes
and translates the audio to English with the same API key used for everything else.

- reply starts with `I heard: "..."` so the resident can catch a mis-heard word; the response also has `transcript`
- complaints keep the original recording; service/rules/announcements discard it after transcribing
- typed text in Hindi/Odia/etc. is translated to English by Gemini and stored as the canonical text
  (original kept in `raw_text`, language detected into `original_language`; voice notes get `und`)
- `GET /api/complaints/<id>/audio` plays a recording: owner + committee/secretary only
- accepted formats: mp3, m4a, mp4, wav, webm, ogg, opus (Android WhatsApp), flac; max 10 MB

## Test
```bash
curl -X POST http://localhost:5000/api/chat/message -H "Authorization: Bearer $RTOKEN" -F "selected_type=complaint" -F "audio=@hi2.ogg"
curl -s -H "Authorization: Bearer $RTOKEN" -o heard.ogg http://localhost:5000/api/complaints/ID/audio && file heard.ogg
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"selected_type": "complaint", "text": "पार्किंग में पानी का रिसाव है"}'
```
Check `transcript` / `translated_text` are correct English. Failure paths return clean JSON:
`unsupported_audio_type`, `text_and_audio`, `no_speech_detected` (422), `speech_failed` (502).

## Known gaps
- Voice recordings are kept as long as their complaint exists; there is no retention/deletion policy yet.
  Step 7's weekly cleanup only clears chat transcripts and must leave the `instance/audio` folder alone.
- Translate-on-read (showing each resident announcements/complaints in their own language) is still ahead.
