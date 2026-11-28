CREATE TABLE IF NOT EXISTS aliases (
    kind text NOT NULL,
    alias text NOT NULL,
    urn text NOT NULL,
    PRIMARY KEY (kind, alias)
);
CREATE TABLE IF NOT EXISTS reconciliation_queue (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category text NOT NULL,
    subject text NOT NULL,
    observed_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz
);

