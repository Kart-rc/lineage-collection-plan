# Visible scenarios for build-time collection (D39): onboarding a repository, scanning pull requests and merges,
# and adding a technology through the extractor plugin contract.

Feature: Any repository joins the lineage with one change

  @S-BC-01 @XC-7
  Scenario: The demo monorepo is onboarded in one change
    Given a fork of the demo at tag 3.1.0 with no lineage configuration
    When one pull request adds fixtures/otel-demo-3.1.0/onboarding/opentelemetry-demo.lineage.yaml as .lineage.yaml and the lineage-ci step to CI
    And the pull request merges
    Then the first merged scan of the default branch completes within 1 hour
    And its unit manifest lists one unit per configured service and schema, 16 in all
    And every later pull request and merge is scanned without further configuration

  @S-BC-02 @XC-7
  Scenario Outline: A wrong onboarding file never fails the build, and says what to fix
    When a pull request adds the invalid file <file>
    Then lineage-ci validate reports the field <field> and how to fix it
    And the CI step exits 0 and the build passes

    Examples:
      | file                                                                          | field         |
      | fixtures/otel-demo-3.1.0/onboarding/invalid/missing-owner.lineage.yaml        | owner         |
      | fixtures/otel-demo-3.1.0/onboarding/invalid/service-name-not-runtime-form.lineage.yaml | services[0].name |
      | fixtures/otel-demo-3.1.0/onboarding/invalid/unknown-extractor.lineage.yaml    | services[0].extractors[0] |
      | fixtures/otel-demo-3.1.0/onboarding/invalid/over-budget.lineage.yaml          | build.max_minutes |
      | fixtures/otel-demo-3.1.0/onboarding/invalid/nothing-to-scan.lineage.yaml      | services, schemas or projects |

  @S-BC-03 @IN-1 @IN-7 @IA-1
  Scenario: A pull request scan re-reads only what changed, into the overlay, within budget
    Given the demo fork has been scanned at its default branch
    When a pull request changes only src/checkout/main.go
    Then the unit manifest marks the checkout unit extracted and the other 15 units unchanged
    And the evidence carries the PR number and lands in the overlay for that repository and PR
    And the scan, including any build step, finishes within 5 minutes

  @S-BC-04 @IA-6 @XC-7
  Scenario: The step fails open when the platform cannot be reached
    Given the evidence topic is unreachable from CI
    When a pull request is scanned
    Then the step exits 0, the manifest says outcome unavailable, the PR shows "lineage check unavailable" and an alert is raised

  @S-BC-05 @XC-8
  Scenario: A new technology is added without changing the runner
    Given the runner with only the stub extractor installed
    When the dbt extractor package is installed and passes the conformance suite
    And fixtures/otel-demo-3.1.0/onboarding/otel-orders-dbt.lineage.yaml onboards the dbt project
    Then the unchanged runner loads the dbt extractor and scans the four models of fixtures/otel-demo-3.1.0/dbt
    And an extractor that fails any conformance check is refused, with the failing check named

  @S-BC-06 @XC-8 @BL-4
  Scenario: A service no extractor reads is a stated gap, not a silent one
    Given the onboarding file lists the shipping service, written in Rust, with no extractor
    When the default branch is scanned
    Then the manifest reports src/shipping as claimed by no extractor
    And the graph holds a dataset-level opaque edge for shipping with reason UNPARSED_LANGUAGE, confirmed or not by runtime evidence
