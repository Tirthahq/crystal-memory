---
name: a-cached-429-is-not-a-rate-limit
family: D
symptom: I am being rate limited, and backing off does not help
source: crystal-a-cached-429-is-not-a-rate-limit
source_sha: d6785db8d76dbb12592d9c233575706e8bd973083ae4c54ace123ad75f7ee793
derived: 2026-09-18
measured_on: 2026-08-03
arrival:
  - G: it times out every time I try this
---

## Symptom

A read-only public API returns HTTP 429. You add backoff, you honour `Retry-After`, you lower
concurrency. The same requests keep failing, and always the same ones.

## What the instrument said

`HTTP 429 Too Many Requests`, with `Retry-After: 1` and a body reading `Retry later`. Every signal the
server sends describes a rate limiter, and every instinct the word 429 triggers is a throttling
instinct.

## What was actually true

It was a cached error response, replayed from a CDN for minutes at a time. A feed sync silently lost 4
of 23 followed authors this way. Their new posts never reached the feed, the digest or the nightly
report, and a human saw one of the missing articles before the pipeline ever did.

Two things made it invisible for a long time. The error looked like a throttle, so the work went into
throttling. And the fetch loop wrapped each source in `except Exception: pass`, so an author we could
not read rendered identically to an author who had published nothing.

## The rival, and the discriminator

**Rival:** a genuine rate limiter.
**Why it is hard to separate:** the status code, the `Retry-After` header and the body all assert the
rival, and a real limiter would also produce failures under load.

**Discriminator, in three steps, each of which could have gone the other way:**

1. **Determinism and item-specificity.** The same four failed on every run, and still failed when
   fetched alone with 3 seconds between them, while other sources returned 200 seconds later. A rate
   limiter is not item-specific.
2. **Vary something that cannot possibly affect a limiter.** For one failing source, `per_page` values
   of 1, 2, 4, 5, 8 and 10 all returned 200, and only `per_page=3` returned 429. Page size cannot
   provoke a counter. That points at keyed storage.
3. **Read the headers.** The 429 carried `age: 359` and `x-cache: MISS, HIT` via `varnish`. A 429 had
   been stored against that exact URL and was being served for about six minutes.

## The one-line check

Read `age`, `x-cache` and `via` on the failing response before you tune anything. A non-zero `age` on
an error means you are arguing with storage, not with a counter.

## The tell

A *subset* of items fails *consistently* across runs of a network sweep, while the rest succeed. That
shape is not what throttling looks like. Stop tuning concurrency and backoff and ask whether the
response is coming from a cache.

Two traps on the way out. A conventional cache-buster does not work: appending a random query parameter
returned the same cached 429 with `age` still climbing. Only a parameter the origin actually varies on
produced a different key, so test your buster before trusting it, because an ineffective one looks
exactly like a real outage. And be careful about the mechanism you claim. We first wrote that the CDN
normalises unknown query parameters out of the cache key. That was an unverified story told in the same
flat voice as the measurements. What was actually established is narrower and sufficient: that buster
did not change the response. Trust the observation, not the explanation of it.
