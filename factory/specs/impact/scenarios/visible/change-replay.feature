# Visible scenarios for O3, change impact. The cases are in fixtures/otel-demo-3.1.0/change-replay.json:
# C1 to C7 from the demo's history and the twin, C8 to C13 authored on 3.1.0 plus the thin dbt model.
# The holdout corpus (at least 7 more changes) is written by people outside this repository; see factory/oracle/holdout.

Feature: A pull request shows what it breaks before it merges

  @S-IA-01 @IA-2 @IA-3 @IA-4 @IA-5 @IA-8
  Scenario: Retyping the shipping zip code is breaking, and the gate blocks it (C1)
    Given the graph at the base of change C1, with the orders topic at tier 1 and its readers confirmed at runtime
    When a pull request against the demo fork retypes Address.zip_code from int32 to string in pb/demo.proto
    Then the report lists one change of kind retyped on kafka://otel-demo/orders#shipping_address.zip_code and on the PlaceOrder request
    And the change class is breaking, because int32 and string are not wire-compatible
    And the downstream list contains postgres://astronomy-db/astronomy_db.accounting.shipping#zip_code, shipping, frontend and load-generator
    And every row has an owner, a tier, an edge state and a confidence
    And value impact and row-set impact are listed separately
    And the contract gate fails the check, citing orders.contract.yaml (BACKWARD_TRANSITIVE)
    And the production graph is unchanged

  @S-IA-02 @IA-3
  Scenario: A package rename breaks builds but not the bytes on the topic (C2)
    When a pull request renames the protobuf package from hipstershop to oteldemo
    Then no element edge changes, because field numbers and types are unchanged
    And the report classes the change potentially breaking, with the reason "wire-compatible; every generated client must regenerate"
    And the gate warns and does not block

  @S-IA-03 @IA-3 @IA-4
  Scenario: A schema move is breaking for every reader of the old names (C4, replayed with the dbt model present)
    Given the thin dbt model reads accounting.order, accounting.orderitem and accounting.shipping
    When a pull request moves the three tables to another schema and updates only the accounting service
    Then the report lists the three tables as renamed
    And the downstream list contains stg_orders, stg_order_items, stg_shipping and fct_order_value
    And the class is breaking for those readers

  @S-IA-04 @IA-3
  Scenario: Formatting is not a change (C8)
    When a pull request reformats models/marts/fct_order_value.sql without changing its logic
    Then every element edge and every expression hash is identical
    And the change class is non-breaking and the gate passes

  @S-IA-05 @IA-3
  Scenario: A change the platform cannot read is reported as unknown (C9)
    When a pull request changes the Ruby email service's confirmation template
    Then the report lists the change as unknown, with the lineage gap at the email hop named
    And it is treated as potentially breaking: the gate warns

  @S-IA-06 @IA-2 @IA-3 @IA-5 @IA-8
  Scenario Outline: Authored field changes are classified and their readers listed
    When a pull request makes change <change>
    Then the change kind is <kind> and the class is <class>
    And the downstream list contains every element in expected_readers for <change>
    And the gate result is <gate>

    Examples:
      | change | kind     | class                | gate  |
      | C10    | renamed  | breaking             | block |
      | C11    | retyped  | breaking             | block |
      | C12    | removed  | breaking             | warn  |
      | C13    | added    | non_breaking         | pass  |

  @S-IA-07 @IA-1
  Scenario: The report arrives within 5 minutes
    Given the PR bot watches the demo fork in the twin
    When 20 pull requests from the change corpus are opened over an hour
    Then at the 95th percentile each report is posted within 5 minutes of the PR opening or updating

  @S-IA-08 @IA-6
  Scenario: The check fails open when the platform is down
    Given the lineage graph store is stopped
    When a pull request opens
    Then the check passes with the comment "lineage check unavailable"
    And an alert is raised to the platform team

  @S-IA-09 @IA-7
  Scenario: A disputed row drops to candidate until reviewed
    Given the report for C1 lists load-generator as a reader
    When the PR author marks that row "this is wrong"
    Then the edge state becomes disputed and its confidence is reported as candidate
    And a review item goes to the owner of load-generator in catalog.yaml

  @S-IA-10 @IA-9
  Scenario: A coding agent asks what a change would break before any PR exists
    When an agent calls /impact with urn kafka://otel-demo/orders#items[].item.quantity and change retyped
    Then the response equals the downstream list for C11
    And the response validates against factory/specs/query-api/interfaces/openapi.yaml
