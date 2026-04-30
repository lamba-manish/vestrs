# vestrs-web

Next.js 15 App Router frontend, **static export only** (`output: 'export'`).
SSR, server actions, and middleware are forbidden in this codebase. See
[`../../CLAUDE.md`](../../CLAUDE.md).

## Local development

```bash
pnpm install
cp .env.example .env
pnpm dev
```

## Production build

```bash
pnpm build   # produces ./out (Caddy serves this directory in prod)
```
