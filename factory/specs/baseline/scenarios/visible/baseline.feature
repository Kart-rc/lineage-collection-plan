# Visible scenarios for O1, baseline lineage, on the reference slice (OpenTelemetry Demo 3.1.0 and the thin dbt model).
# Tags: the first tag is the scenario ID; requirement IDs follow. Fixtures are paths in this repository.

Feature: Baseline element lineage on the order flow

  @S-BL-01 @BL-1 @BL-2 @BL-3 @BL-6
  Scenario: Checkout's assembly of the order is found field by field
    Given the demo source at tag 3.1.0
    And the golden graph fixtures/otel-demo-3.1.0/golden-graph.json
    When the service field scanner reads src/checkout/main.go
    Then it emits one DERIVES element mapping per golden edge from main.go, 18 in all
    And each mapping carries class, subtype, an expression hash and the extractor name and version
    And api://otel-demo/checkout/PlaceOrder/request#address.zip_code maps to kafka://otel-demo/orders#shipping_address.zip_code as DIRECT IDENTITY, citing main.go line 387
    And field precision and recall on the checkout hop are both at least 0.90

  @S-BL-02 @BL-2 @BL-3
  Scenario: Accounting's ORM writes are found column by column
    Given the demo source at tag 3.1.0
    When the ORM writer extractor reads src/accounting/Consumer.cs and its entity classes
    Then it emits the 17 golden edges into accounting."order", accounting.orderitem and accounting.shipping
    And kafka://otel-demo/orders#shipping_address.zip_code maps to postgres://astronomy-db/astronomy_db.accounting.shipping#zip_code, citing Consumer.cs line 126
    And precision and recall are both at least 0.95

  @S-BL-03 @BL-1
  Scenario: Every protobuf field on the slice is a node
    Given pb/demo.proto at tag 3.1.0
    When the protobuf extractor reads the compiled descriptors
    Then every api:// and kafka:// element in the golden graph exists as a node
    And repeated fields use [] in the path, as in kafka://otel-demo/orders#items[].cost.units

  @S-BL-04 @BL-4
  Scenario: A unit no rule can read becomes an opaque edge, not a silent gap
    Given the email service is Ruby and no rule set reads Ruby in wave 2
    When the service field scanner reaches checkout's call to email /send_order_confirmation
    Then it emits a dataset-level edge from api://otel-demo/checkout/PlaceOrder/request to svc://otel-demo/email
    And the edge carries opaque reason UNPARSED_LANGUAGE
    And the coverage report counts one lineage gap at the email hop

  @S-BL-05 @BL-5
  Scenario: Join and group-by keys are stored once for the table, not once per column
    Given the thin dbt model fixtures/otel-demo-3.1.0/dbt and its golden edges golden-dbt.json
    When the dbt and SQL extractor reads models/marts/fct_order_value.sql
    Then it emits 4 indirect edges into postgres://astronomy-db/astronomy_db.analytics_marts.fct_order_value: 3 JOIN on order_id and 1 GROUP_BY
    And the graph stores 5 indirect edges for the whole model set, not 35
    And no indirect edge points at an individual column of fct_order_value

  @S-BL-06 @BL-6 @BL-3
  Scenario: The baseline meets its accuracy bar once runtime evidence is on
    Given the twin has run for at least 10 minutes with the capture add-on
    And every extractor of waves 1 and 2 has run on the slice
    When lineage-eval scores the graph against golden-graph.json and golden-dbt.json
    Then field-edge precision is at least 0.90 and recall at least 0.90
    And service and topic edges reach precision 0.95, recall 0.90 and all 13 upstream-asserted edges

  @S-BL-07 @BL-7
  Scenario: Rebuilding from the archive gives the same graph
    Given the live graph at a recorded time T
    When the graph is rebuilt from the raw archive up to T into an empty store
    Then the rebuilt graph's hash equals the live graph's hash
    And this holds on 3 of 3 rebuilds

  @S-BL-08 @BL-6 @XC-3
  Scenario: Service edges come from traces, and Kafka hops from the topic name
    Given the capture of 27 November in which producer and consumer spans are in separate traces
    When the service edge builder reads traces.jsonl
    Then it reports checkout PRODUCES kafka://otel-demo/orders and orders CONSUMES by accounting and fraud-detection
    And it uses no trace link to find them
    And calls to flagd are reported as configuration reads, not as data edges
    And reading telemetry never adds latency to any request path

  @S-BL-09 @BL-1
  Scenario: Every name in a capture resolves, and no IP address becomes an identity
    Given the alias table fixtures/otel-demo-3.1.0/aliases.json
    When the resolver reads every addressing name in the capture's traces, logs and metrics
    Then all 55 distinct names resolve to a URN or are declared non-entities
    And checkout's calls to 172.18.0.x are resolved through the callee's server span, never through the address
    And astronomy_user, the shared database login, is never used to attribute access
