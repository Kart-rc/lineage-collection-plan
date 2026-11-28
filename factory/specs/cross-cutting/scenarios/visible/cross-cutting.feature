# Visible scenarios for the cross-cutting requirements and the must-not-flow rules (D11, D30).

Feature: Safe, traceable and open by construction

  @S-XC-01 @XC-1
  Scenario: Only metadata is stored
    Given evidence collected during both twin runs, including accounting's batched INSERT statements
    When the raw archive and the graph are scanned
    Then they contain names, schemas, expressions, counts and times only
    And no parameter value, no email address and no card number is found

  @S-XC-02 @XC-2
  Scenario: Every edge traces to its raw input and the tool that produced it
    Given 50 edges sampled from the graph
    When /explain is called for each
    Then every edge lists its evidence records, and every record has a rawRef that exists in the archive and a producer with a version

  @S-XC-03 @XC-3
  Scenario: The platform never slows a producer
    Given the evidence broker is stopped
    When checkout handles orders for 10 minutes
    Then checkout's p99 latency rises by less than 1 ms and no request fails because of lineage

  @S-XC-04 @XC-4
  Scenario: OpenLineage column facets survive a round trip
    Given OpenLineage run events with column lineage facets from the complement's Feast materialization
    When they are ingested and emitted again
    Then every input field, output field, class and subtype equals the original

  @S-XC-05 @XC-5
  Scenario: Personal fields are shown only to roles allowed to see them
    Given accounting.shipping#street_address, #city and #zip_code are classified personal in accounting.contract.yaml
    When a user without the personal-data role calls /impact on kafka://otel-demo/orders#shipping_address.zip_code
    Then the personal elements are returned without values or samples, flagged personal, and their lineage is still shown

  @S-XC-06 @XC-6
  Scenario: Code sent to a model leaves only through the approved endpoint
    Given the model-assisted extractor reads the Ruby email service
    When it runs
    Then only source code and schemas are sent, and only to the Bedrock endpoint in the platform account (D19)
    And every resulting event records the model, the prompt version and the output hash

  @S-XC-07 @IA-5
  Scenario Outline: Must-not-flow rules hold on active and latent edges
    Given the five rules in golden-graph.json under must_not_flow
    When the gate checks rule <rule>
    Then no active path exists from <from> to <to>
    And a latent path, if any, is reported with its condition before the condition can become true

    Examples:
      | rule | from                                   | to                                                  |
      | 1    | PlaceOrder/request#credit_card.*       | kafka://otel-demo/orders                            |
      | 2    | PlaceOrder/request#credit_card.*       | postgres://astronomy-db/astronomy_db.accounting.*   |
      | 3    | PlaceOrder/request#email               | kafka://otel-demo/orders                            |
      | 4    | PlaceOrder/request#credit_card.credit_card_cvv | otel://otel-demo/otel-collector/traces      |
      | 5    | PlaceOrder/request#email               | otel://otel-demo/otel-collector/traces#user.email   |

  @S-XC-08 @XC-1 @IA-5
  Scenario: The latent card path into telemetry is visible before the flag is switched on (C7)
    Given emitRawPii is off
    When the gate evaluates must-not-flow rule 4
    Then it reports the latent path from the card CVV into checkout's span attributes, conditioned on flag://otel-demo/emitRawPii == on
    And it reports that the collector's delete of demo.payment.card_cvv (otelcol-config.yml:222) stops it before the export
