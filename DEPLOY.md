# Deployment

Production runs as six containers behind nginx: the site, a Celery worker, a
Celery scheduler, PostgreSQL, Redis, and a one-shot migration job. Pictures and
static files live in a Cloudflare R2 bucket, not on the machine.

## Requirements

- Docker Engine 24+ with the compose plugin
- A Cloudflare R2 bucket and an API token for it
- An SMTP account (Resend)
- 6 GB of free RAM (see the memory table below) and 10 GB of disk
- Ports 80 and, for https, 443

## 1. Configure

```
cp .env.example .env
```

Fill in every value. These stop the stack from starting if missing:

| Variable | Notes |
|---|---|
| `SECRET_KEY` | A dollar sign is eaten by compose - double it as `$$` or avoid it |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Must agree with `DATABASE_URL` |
| `DATABASE_URL` | `postgresql://user:password@db:5432/dbname` |
| `REDIS_PASSWORD` | Any long random string |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | The names people will type |
| `R2_ACCOUNT_ID`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Refused at startup if empty |
| `RESEND_API_KEY`, `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL` | |

## 2. Start

```
make prod-deploy
```

Builds the images, applies migrations in a one-shot job, starts everything, and
restarts nginx last. The restart is required, not cosmetic: nginx resolves the
site container's address once, at its own start, and a rebuilt container comes
back on a different address.

## 3. Upload the static files

```
make prod-collectstatic
```

Once per deploy that changed CSS, JavaScript or fonts. The files are served from
the bucket, not by nginx, so the site renders unstyled until this has run.

## 4. Create the first account

```
docker compose -f docker-compose.prod.yml run --rm web python app/manage.py createsuperuser
```

## 5. Verify

```
curl -s localhost/healthz/
docker compose -f docker-compose.prod.yml ps
```

The health endpoint answers `{"status": "ok", "checks": {"database": "ok",
"redis": "ok"}}`. Only the database decides the verdict: the site survives a
dead Redis, so that one is reported but never fatal.

Every service reports its own health, and `ps` should show all of them
`healthy`. The migration job is expected to sit at `Exited (0)`.

## Updating

```
git pull
make prod-deploy
make prod-collectstatic   # only if the frontend changed
```

Migrations run on their own, before the site starts. If one fails the site does
not start - which is the point.

## HTTPS

The stack listens on port 80 only. To add https:

1. Put `fullchain.pem` and `privkey.pem` in `nginx/certs/`
2. Uncomment the `443` block in `nginx/nginx.conf`
3. Uncomment the port and the certificate volume in `docker-compose.prod.yml`
4. `make prod-deploy`

To stop answering plain http as well, turn the port 80 server into a redirect.

## Running over http on a development machine

The production stack forces https, sends the year-long HSTS header and refuses
to hand out cookies over http - so `http://localhost` is unusable as it stands.
For a local run without a certificate, set in `.env`:

```
INSECURE_LOCAL_HTTP=true
```

It turns off all three at once. **Never set this on a server**: with it on,
passwords and sessions travel in the clear.

## Showing the site over a tunnel

```
make prod-ngrok        # prints the public https address
make prod-ngrok-down
```

The tunnel ends at nginx, so a guest's request takes the same path a real
visitor's would. The address has to be listed in `ALLOWED_HOSTS` and
`CSRF_TRUSTED_ORIGINS` beforehand.

## Memory

| Service | Limit | Killed first when memory runs out |
|---|---|---|
| database | 2 GB | last |
| site | 2 GB | 4th |
| worker | 1.5 GB | 2nd |
| Redis | 512 MB | 5th |
| scheduler | 256 MB | first |
| nginx | 128 MB | 3rd |

The database is killed last because everything else can be restarted, while it
holds the only copy of the data. Redis is capped at 384 MB internally, below its
container, leaving room for the copy it makes while saving to disk; under
pressure it evicts cache entries only, never the queue or the view counters.

The site runs 5 processes of 2 threads, the worker 4 processes. Both are set
explicitly: the usual "cores × 2 + 1" asks for 33 processes on a 16-thread
machine, each holding its own copy of Django.

## When something is wrong

```
make prod-logs                 # everything, follow
make prod-ps                   # health of each service
make check-deploy              # Django's own audit of the settings
```

**The site answers 502.** nginx is pointing at an address the site container no
longer has. `docker compose -f docker-compose.prod.yml restart nginx`, and use
`make prod-deploy` next time.

**Pages are slow, the log is full of Redis errors.** Redis is down. The site
keeps working: pages render from the database, sign-in is still protected
because failed attempts are counted there. What stops working is anything that
schedules background work - uploads, registration - and those answer 503 rather
than half-finishing.

**Uploads answer 503.** The queue is unreachable. Nothing was written; the
request can simply be repeated once Redis is back.

**A picture never downloads.** The bookmarked link is fetched by the worker.
Check `make prod-logs` for `download_image`; the failure reason is also shown on
the picture's own page.

## Backups

Not automated. The database is the only thing that cannot be rebuilt:

```
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql
```

Pictures live in the bucket and are covered by whatever retention it has.

## Notes

- Port 80 published to the outside means the forwarded-for header can be
  claimed by anyone who reaches it directly, because published ports arrive
  through docker's own forwarder from inside the network. On a real server put
  this behind a proxy you control and narrow `set_real_ip_from` in
  `nginx/nginx.conf` to its address.
