# Visible scenarios for O2, incremental lineage, on the reference slice. Change IDs refer to change-replay.json.

Feature: Lineage stays current as code, schemas and flags change

  @S-IN-01 @IN-1
  Scenario: Only changed units are re-extracted
    Given the graph built at demo tag 3.1.0
    When the commit of change C1 (133d089, zip_code retyped) lands on the default branch
    Then the extractors are called only for units whose content hash, input schema hash or extractor version changed
    And the extractor call count equals that number exactly

  @S-IN-02 @IN-2
  Scenario: A unit's static evidence is replaced as one set
    Given stg_order_items in the thin dbt model supports 9 direct element edges
    When the model is changed to drop line_total and re-extracted
    Then the 3 edges into stg_order_items#line_total close in one atomic write
    And the other 6 direct edges stay open with unchanged versions

  @S-IN-03 @IN-2
  Scenario: A broken extractor release is held, not written
    Given the ORM writer extractor supports 17 edges into the accounting tables
    When a faulty extractor version re-extracts accounting and would close 12 of them
    Then the write is held because it would close more than 20% of the extractor's edges and at least 10 edges
    And an alert names the extractor version and the unit
    And the graph is unchanged until a person releases or rejects the write

  @S-IN-04 @IN-3
  Scenario: A column added upstream reaches a SELECT * model
    Given stg_shipping is "select * from accounting.shipping"
    When a column delivery_window is added to accounting.shipping and its DDL change is registered
    Then a schema-change event is published for postgres://astronomy-db/astronomy_db.accounting.shipping
    And every unit that reads accounting.shipping is re-extracted, stg_shipping included
    And stg_shipping#delivery_window appears with one DIRECT IDENTITY edge from accounting.shipping#delivery_window

  @S-IN-05 @IN-4 @IN-5
  Scenario: A schema move closes old edges and opens new ones without losing history (C4)
    Given the graph at the commit before change C4, with tables in the public schema
    When change C4 (5f83ad1) moves order, orderitem and shipping into the accounting schema
    Then every edge into public.order, public.orderitem and public.shipping gets a valid_to at the change
    And the same edges into accounting."order", accounting.orderitem and accounting.shipping open at the change
    And the graph read as of a time before C4 still shows the public tables
    And no edge version is updated in place

  @S-IN-06 @IN-5
  Scenario: Late access history lands in the past, not now
    Given access history for 14:00 that arrives at 16:00
    When it is ingested
    Then the edges it supports are valid from 14:00 and recorded at 16:00
    And the graph as recorded at 15:00 does not show them, while the graph valid at 14:30 read now does

  @S-IN-07 @IN-6
  Scenario Outline: The diff between two commits matches the hand-written expected diff
    Given the graph at the base commit of <change>
    When the diff to its head commit is requested
    Then the added, removed and changed edges equal the expected diff for <change>, with the evidence that caused each

    Examples:
      | change | what the diff must show |
      | C3     | 17 element edges and 3 tables added, nothing removed |
      | C4     | edges re-pointed from public.* to accounting.*, closed and opened at the same time |
      | C5     | product-reviews and its edges retired, not deleted |
      | C7     | 5 flag-gated edges moved from latent to active, with the flag change as the cause |

  @S-IN-08 @IN-7
  Scenario: A pull request's evidence stays in its overlay
    Given an open pull request against the demo fork that renames shipping_tracking_id
    When its static evidence is extracted
    Then it is stored in the overlay for that repository and PR number
    And production impact and RCA queries do not see it
    And the production graph's hash is unchanged

  @S-IN-09 @IN-8
  Scenario: An edge with no runtime evidence for 30 days goes dormant
    Given the edge frontend CALLS shipping, supported by code and never seen at runtime after day 0
    When the clock advances 30 days
    Then the edge state becomes dormant and the edge is kept

  @S-IN-10 @IN-9
  Scenario: The same evidence twice changes nothing
    Given the evidence from the 27 November capture has been ingested
    When the same events are delivered again in a different order
    Then the graph hash is unchanged and no lineage.changes event is emitted

  @S-IN-11 @IN-10
  Scenario: A merged change is visible within 15 minutes
    Given the twin with the lineage platform running
    When 20 changes are merged and run over an hour
    Then at the 95th percentile each resulting edge is visible within 15 minutes of its merge or run

  @S-IN-12 @IN-2 @IN-6
  Scenario: A flag changes lineage with no code change (C7)
    Given the edges from checkout and payment into span attributes carry the condition flag://otel-demo/emitRawPii == on
    And the flag is off, so the 5 edges are latent
    When the change event "emitRawPii off -> on" arrives
    Then the 5 edges become active, with the change event as their cause
    And the collector's 3 masking edges start carrying the hashed email and the masked card numbers
    And when the flag returns to off the 5 edges become latent again

  @S-IN-13 @IN-6
  Scenario: A rewrite in another language changes no lineage (C6)
    Given recommendation CALLS product-catalog, supported by Python code at 3.1.0
    When change C6 (c7b195f) rewrites recommendation in Java
    Then the edge stays open with its static evidence now pointing at the Java source
    And the diff reports no lineage change
