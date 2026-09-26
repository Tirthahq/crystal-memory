---
name: no-expected-duration-means-no-silence-looks-wrong
family: A
symptom: The output is still empty, so the background job must still be working
source: crystal-a-dispatch-with-no-expected-duration-cannot-surprise-you
source_sha: 7da04ac3306f6220d7a391166b55eaca8bfbd7778f96706c2199bdb7a6757522
derived: 2026-09-26
measured_on: 2026-09-25

---

## Symptom

You hand a long task to a coding-agent CLI in the background and get on with something else. Later you
look, see no output yet, and conclude it is still working.

## What the instrument said

The run was checked once, at ten minutes. The visible output was empty, and empty looked like progress.
Nobody checked again for over an hour.

## What was actually true

**The run had been blocked from its first second, and the evidence was in its output file at 45
seconds.** It had been waiting for input for 75 minutes. Two things made a blocked run and a working run
look the same from outside:

- The CLI still reads standard input even when the prompt is passed as an argument. Launched from a
  caller that leaves stdin open, it prints one line saying it is reading additional input, and waits
  forever.
- The output was piped through `| tail`, which buffers everything until the process exits. A working
  run and a blocked one both show nothing until the end, so the pipe erased the one difference.

But neither of those was the failure. **No expected duration had been stated**, so 5 minutes and 75
minutes were equally consistent with "still working", and no elapsed time could ever have looked
wrong enough to go and check.

## The rival, and the discriminator

**RIVAL:** it is a long task and it is simply still running. Real investigations do take many minutes.

**DISCRIMINATOR:** the GROWTH of the output file, not its content. A blocked run stayed at 39 bytes. A
working run opened with the very same stdin line, received end-of-file, and continued: 39 bytes, then
151,928. A slow run grows; a blocked one does not. The first version of the guard for this grepped for
the stdin line instead, and failed a run that was working perfectly, because the message is present
in both.

## The one-line check

**State the bound at dispatch** ("first output within 60 seconds, or something is wrong"), send stdin
from `/dev/null`, redirect output to a FILE rather than through `tail`, and poll the file's size:

```
agent-cli "<prompt>" < /dev/null > run.log 2>&1 &
# past the bound: is run.log still the same size? then that is an answer, not a wait
```

Bound the FIRST byte, not completion. Completion is legitimately long; blocking shows at the start.

## The tell

**You are about to say "no output yet, it is probably still working."** Without a bound written down,
that sentence is true at every elapsed time, which means it carries no information. Past the bound,
an empty output file is a finding.
