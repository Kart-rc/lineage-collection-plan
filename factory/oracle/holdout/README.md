# Holdout: custody rules

There are no holdout cases in this repository, and there must never be. Builders are agents that read this repository; a holdout case they can read is a visible case.

## Who writes them

A person who does not build, or an agent run with no access to the build repositories and no write access here. The platform lead approves them at G3.

## Where they live

A separate store the build sandboxes cannot read: a private repository or bucket with its own access list. The harness reads it in a separate job and returns only a pass rate and failure categories per family.

## What they must cover

For each family listed under `corpora` in `factory/parameters.yaml`, at least one third of that family's cases, and at least 7 changes and 7 incidents in total. They are siblings of visible cases, not copies: a retype instead of a rename, the same rename made in the dbt model instead of the proto, the same failure on a different service, or a decoy at a different time.

## What the holdout must include (D38)

- Near-simultaneous changes on different dependencies of the same failing node. In the visible runs the incidents were nine minutes apart, so time alone often decided the ranking.
- At least one silent failure and one cause that comes from callers, so the coverage findings and the reported limitation are tested.
- At least one flag flipped through a targeting rule.

## What is already public, and so cannot be holdout

- The four changes named in decision D15 (rename `shipping_tracking_id`, retype `quantity`, remove a column from `accounting.shipping`, add a field). They are now visible cases C10 to C13.
- Everything in `change-replay.json` and `incident-scenarios.json`, and every scenario under `factory/specs/*/scenarios/visible/`.
- The flag names and variants in the demo's `src/flagd/demo.flagd.json`. Holdout incidents can use them, but in combinations, variants, timings or services not used by a visible case.
