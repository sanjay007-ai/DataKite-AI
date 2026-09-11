# DataKite AI — Free AI setup

DataKite can use a real Gemini model for natural-language answers. Users of your website do not need their own API key; the server uses the `GEMINI_API_KEY` environment variable.

## Free mode
Google currently provides a Gemini Developer API Free Tier with free input/output token pricing for supported models, subject to model and rate limits. This is a provider free tier, not an unlimited guarantee.

Set these server environment variables:

```text
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash-lite
DATAKITE_SECRET_KEY=use-a-long-random-secret
```

Never put the API key in frontend JavaScript or commit it to Git.

If `GEMINI_API_KEY` is absent or the free-tier limit is reached, DataKite automatically falls back to its built-in deterministic analytics engines instead of breaking the chat.

Official setup and pricing:
- https://ai.google.dev/gemini-api/docs/get-started
- https://ai.google.dev/gemini-api/docs/pricing
