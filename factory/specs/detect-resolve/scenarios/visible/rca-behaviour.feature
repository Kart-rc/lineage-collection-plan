# Visible scenarios for O4 behaviour that is not a single incident replay. Incident replays are in incident-replay.feature.

Feature: From a failing check to the cause and a plan

  @S-IR-01 @IR-2
  Scenario: The walk uses every edge valid in the incident window, including one that closed
    Given an incident window from 14:20 to 14:40
    And the edge accounting WRITES public.shipping closed at 14:30 when change C4 moved the tables
    When the upstream walk starts from a check failing at 14:40 on stg_shipping
    Then the walk includes the closed edge to public.shipping and the open edge to accounting.shipping
    And it does not use the graph as of 14:40 alone

  @S-IR-02 @IR-2
  Scenario: An edge that changed after the incident does not hide the cause
    Given incident I1 ended at 14:30:09
    When an unrelated change opens a new edge into payment at 15:00 and the walk is replayed afterwards for the window up to 14:30
    Then the walk and the ranking are identical to the replay made before 15:00

  @S-IR-03 @IR-3
  Scenario: The first failing element is the furthest upstream one whose own inputs pass
    Given during I1 the checks on accounting."order" inserts and on the orders topic rate fail
    And checkout errors fail, while nothing checked upstream of payment fails
    When the first failing element is computed
    Then it is svc://otel-demo/payment, reached through checkout's failing calls to it
    And the checks on the topic and the table are reported as downstream symptoms

  @S-IR-04 @IR-4
  Scenario: Every ranked cause shows the terms of its score
    Given the change events of incident I1 and the score in factory/parameters.yaml
    When the ranking is produced
    Then each candidate shows lineage, time, direction and failing_calls terms, the evidence path and any lineage gap
    And the same inputs give the same ranking, 3 of 3 times

  @S-IR-05 @IR-6
  Scenario: The blast radius separates what is already wrong from what is not yet
    Given incident I1 and the scheduled runs in fixtures/otel-demo-3.1.0/dbt/runs-incident-I1.json
    When the blast radius is computed at 14:35
    Then affected holds stg_orders, stg_order_items, stg_shipping and fct_order_value, because orders_mart ran at 14:30
    And not yet affected holds finance_orders_dashboard, which refreshes next at 18:00

  @S-IR-06 @IR-7
  Scenario: The remediation plan follows the graph in order, with an owner per step
    Given incident I1 has been identified with paymentFailure as the cause
    When the remediation plan is produced
    Then its steps are, in order: revert the flag (team-payments, payment), confirm checkout recovers (team-payments), let accounting catch up from the topic (team-finance-data), re-run orders_mart (team-finance-data), refresh finance_orders_dashboard if it ran in between (team-finance-data)
    And the plan matches the stored snapshot

  @S-IR-07 @IR-8
  Scenario: The circuit breaker pauses an opted-in job and waits for a person
    Given orders_mart has opted in to the circuit breaker in fixtures/otel-demo-3.1.0/dbt/jobs.yml
    And kafka://otel-demo/orders, a tier 1 element, is failing its rate check
    When orders_mart is due to run
    Then it is paused and its owner is notified
    And finance_dashboard_refresh, which has not opted in, is not paused
    And an attempt to resume orders_mart without a person's instruction is refused

  @S-IR-08 @IR-9
  Scenario: Each incident records its four times and compares with the run without lineage
    Given incident replays run twice, once with lineage and once without (D16)
    When each replay ends
    Then each has the times bad data landed, the alert fired, the cause was identified and remediation completed
    And the report shows time to detect and time to resolve with and without lineage for each incident
