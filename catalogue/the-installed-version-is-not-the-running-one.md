---
name: the-installed-version-is-not-the-running-one
family: C
symptom: The version check says I am current and a feature says I need to update
source: crystal-the-installed-version-is-not-the-running-one
source_sha: a151adfd1cec6c1f6b7a4dd291f1ac78879cea12e7712181a8d9b32458a334a1
derived: 2026-09-26
measured_on: 2026-09-26

---

## Symptom

A feature refuses to work and tells you to update to a newer version. You check the version, it is
already newer than the one asked for, and the feature still refuses.

## What the instrument said

Two readings, taken minutes apart, inside the same long-running agent session:

| the reading | what it said |
|---|---|
| the feature's own gate | disabled: update to 2.1.280 or later |
| `<tool> --version` | 2.1.283 |

Both were true. The obvious conclusion was that the gate was wrong.

## What was actually true

**`<tool> --version` starts a NEW process from the binary on disk. The session you are typing into is
the process that was started days ago.** The install had been updated that morning; the session had
been running for nine days. The gate read the build that was actually executing, and it was right.

The version check answered a question nobody had asked ("what is installed?") and it answered it
correctly. The question that mattered was "what is running?", and the command does not name which of
the two it reports.

## The rival, and the discriminator

**RIVAL:** the feature gate is buggy, or caching a stale flag, since the version check shows a new
enough build.

**DISCRIMINATOR:** compare two timestamps. When did the install change, and when did this process
start?

```
ls -l "$(command -v <tool>)"      # when the installed binary (or its symlink) last moved
ps -o lstart= -p $PPID            # when the process you are inside started
```

The process was older than the install. A buggy gate predicts the two would agree and the feature would
still refuse; a stale process predicts exactly the split that was observed, and a restart would clear
it. Only a restart adopts the new build.

## The one-line check

Before believing a version check about the thing you are running inside, **check that the process is
younger than the install.** If it is older, every check you run from inside it reports the new version
while you keep running the old one.

## The tell

**A feature insists it needs a version you appear to already have.** Believe the feature first, then go
and find out which build is actually executing. It is the same shape as the rest of this family: a
right answer about the wrong population. "Installed" and "running" are two populations, and the
command names neither.
