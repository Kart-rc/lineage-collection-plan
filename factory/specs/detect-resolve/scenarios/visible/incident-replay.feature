# Visible incident replays for O4, run in the twin on 27 November 2026 (I1 in the first run, I2 to I10 in the second,
# with 15 simulated shoppers). Each scenario states what the system must do; the observed run is the evidence that the
# scenario is satisfiable. Change events and check results: fixtures/otel-demo-3.1.0/capture-2026-11-27/.
# The holdout corpus holds siblings of these (other variants, services, timings and decoys), outside this repository.

Feature: From a failing check to the change that caused it

  Background:
    Given the checks in fixtures/otel-demo-3.1.0/checks.yaml, with thresholds fixed before the run
    And the RCA score in factory/parameters.yaml
    And every change event of the run on the timeline, including changes that injected nothing

  @S-IR-10 @IR-1 @IR-3 @IR-4 @IR-5
  Scenario: Payments fail half the time (I1)
    When paymentFailure is set to 50%
    Then checkout-errors fails within 3 minutes
    And the walk from checkout finds failing calls ending at payment
    And paymentFailure ranks first, above emitRawPii, which payment also reads, and its revert
    And the path, the ranked causes and the blast radius are attached to the alert within 2 minutes of the failing check

  @S-IR-11 @IR-1 @IR-5
  Scenario: The orders topic is flooded and its consumers lag (I2)
    When kafkaQueueProblems is switched on
    Then orders-rate, fraud-detection-lag and accounting-lag fail within 3 minutes
    And kafkaQueueProblems ranks first

  @S-IR-12 @IR-1 @IR-3 @IR-5
  Scenario: A lock on catalog.products slows the catalog and breaks checkouts (I3)
    When productCatalogLockContention is switched on
    Then checkout-errors fails within 3 minutes, and product-catalog-latency after it
    And the walk from checkout finds failing calls ending at product-catalog
    And productCatalogLockContention ranks first, above earlier changes to the same service

  @S-IR-13 @IR-1 @IR-5
  Scenario: The accounting consumer stops (I7)
    When the accounting service is stopped for 4 minutes
    Then accounting-order-rate fails within 3 minutes while orders-rate keeps passing
    And the stop event for svc://otel-demo/accounting ranks first
    And when accounting starts again the check passes once the backlog is written

  @S-IR-14 @IR-1 @IR-5
  Scenario: Checkout calls a payment address that does not answer (I4)
    When paymentUnreachable is switched on
    Then checkout-errors fails within 3 minutes and orders-rate after it
    And paymentUnreachable ranks first, although no failing call reaches a payment server span

  @S-IR-15 @IR-1 @IR-3 @IR-5
  Scenario: One product cannot be read, and orders that contain it fail (I6)
    When productCatalogFailure is switched on through its targeting rule for product OLJCESPC7Z
    Then checkout-errors fails within 3 minutes
    And productCatalogFailure ranks first
    And the earlier change to the same flag's default variant, which injected nothing, ranks below it

  @S-IR-16 @IR-1 @IR-5
  Scenario: International shipments are delayed (I8)
    When intlShippingSlowdown is set to 10sec
    Then checkout-latency fails within 3 minutes while checkout-errors keeps passing
    And intlShippingSlowdown ranks first

  @S-IR-17 @IR-4 @IR-5
  Scenario: A decoy outside the lineage does not outrank the cause (I9)
    When recommendationCacheFailure is switched on, and one minute later paymentFailure is set to 25%
    Then checkout-errors fails within 3 minutes
    And paymentFailure ranks first with a lineage term of 1.0
    And recommendationCacheFailure, which no node on checkout's path reads, scores a lineage term of 0 and is not in the top three

  @S-IR-18 @IR-1 @IR-9
  Scenario: A silent failure is reported as a coverage gap, not as a quiet success (I5)
    When cartFailure is set to 50%, which makes EmptyCart fail and checkout ignore it
    Then no check registered for the slice fails, and no alert is raised
    And the incident record shows the bad data landing with no detection time, counted against IR-5
    And the weekly review gets a coverage finding: no check watches items per order or cart state

  @S-IR-19 @IR-4 @IR-9
  Scenario: A cause that comes from callers is out of the dependency walk's reach (I10)
    When loadGeneratorFloodHomepage is switched on
    Then the incident record shows the change with no detection time if no check fails
    And if a check does fail, loadGeneratorFloodHomepage scores a lineage term of 0, because the load generator calls the system and is not one of its dependencies
    And the limitation is reported with the ranking, so a person knows to look at traffic as well as lineage
