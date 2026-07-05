# Domain concepts

## Account

A Xiaohongshu account the system can act on behalf of. Each account has one
cookie file at `xiaohongshu-saas/data/cookies/<account_id>.json`. The cookie
file is the source of truth for identity; rotating it = rotating identity.

## Channel

A publisher implementation. Today only `xiaohongshu` is wired end-to-end;
`douyin` exists as a skeleton under `app/channels/douyin/`. New channels
implement the `Channel` protocol in `app/channels/base.py`.

## Note

A single Xiaohongshu post. Fields:

- `id` (uuid)
- `account_id`
- `title`, `body`, `image_paths`
- `topic_id`
- `scheduled_at`, `published_at`, `post_url`
- `status`: `pending` | `publishing` | `published` | `failed`
- `failure_reason`

## Topic

A subject the content factory can generate notes about. Topics are
seeded by the operator and consumed round-robin.

## ContentFactory

A strategy for turning a topic into a note payload. Strategies live in
`app/content_factory/strategies/` (e.g. `listicle`, `single_image`,
`carousel`). Each strategy declares required fields, prompt template, and
image count.

## Template

A Jinja-like text snippet. Stored in `xiaohongshu-saas/data/templates/`.
Referenced by `ContentFactory.strategy_id`.

## Metrics

A row per capture for a published note: `likes`, `comments`, `saves`,
`shares`, captured at `captured_at`. Used for retention analysis.

## Comment

A reply left on either our own posts or target posts. Stores the source
post URL, the generated body, and the timestamp.

## Event

Anything the system wants the console to know about: publish success/fail,
captcha needed, cookie expired, scheduler tick. Streamed through SSE.