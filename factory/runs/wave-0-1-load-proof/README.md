# Candidate 9: observed users and sustained traffic proof

This is the final source repair under the user's approved extension: nine
cumulative attempts, with the existing November 28 20:42 UTC timebox. The six
original attempts, candidate 7's hosted failure and candidate 8's rejected
independent review remain recorded. No new source repair beyond this candidate
is authorized by that extension.

Candidate 8's capacity and OTLP changes passed independent checks, but its pilot
could report success with only one or four users instead of the configured five.
It also accepted a flat request counter throughout the window followed by one
completion at the final sample. That is insufficient evidence of activity across
the full window; it does not prove that no long-running requests were in flight.
The unchanged independent probe and rejected candidate are preserved under
`../wave-0-1-collector-capacity/`.

Only `twin/pilot.py` and its tests change from candidate 8. The pilot now verifies
exactly five observed users at baseline and every sample. It retains 30-second
sampling and requires evidence of request progress within 60 actual monotonic
seconds of window start or the last observed progress. An unchanged immediate
sample is allowed. Progress observed at the 60-second boundary is allowed; flat
at that boundary or progress observed later leaves activity unproven. A later
burst cannot erase an earlier unproven interval. The final probe tail is checked
as well. Reports retain the fixed observation policy, maximum observed interval
and progress verdict using safe metadata.

This is a sufficiency check on the pilot's traffic evidence, not a new throughput
or response-latency objective. Missing progress is categorized as
`load_progress_unproven`; it does not label long in-flight requests inactive.
The actual 600-second window, 900-second startup ceiling, exact precision floor
of 0.95, sustained service health, forwarding, resource caps and cleanup ownership
requirements remain in force.

The 113 focused pilot tests passed. The independent probe's valid five-user
control still passes; one-user, four-user and final-burst cases now block. Prior
candidate 7's actual traffic observations fit this observation policy: every
user count was five and its maximum interval since observed progress was about
30.54 seconds. That historical trial still failed collector health and scoring;
it is not relabeled as acceptance or as a candidate 9 run.

The measured collector profile and canonical OTLP validation from candidate 8
remain unchanged. See its `checks/` for synthetic capacity measurements and
pinned serializer citations. The frozen candidate 9 archive and manifest bind
all eight relevant source files, with exactly two differences from candidate 8.
Independent review and fresh hosted results are separate from these local tests.

Full Wave 0/1 acceptance remains incomplete until the required cold starts,
reference precision, end-to-end timings, independent holdout, applicable original
capture replay and human gates are satisfied. Docker Neo4j Community remains the
authorized database target. Gap recommendations are retained in
`../wave-0-1-collector-capacity/recommendations.md`.
