# OSS reference flows: complements to the OpenTelemetry Demo

Read on 2026-11-27. Purpose: find open-source, runnable systems with a real multi-service data flow to replace the hypothetical card-authorisation-to-fraud-model slice in the build plan, concentrating on the hops the OpenTelemetry Demo lacks (stream processor, warehouse or lakehouse with dbt, feature store, model trained and served from those features). The OpenTelemetry Demo itself is out of scope here (the coordinator is analysing it).

## Method and limits

- Every repository below marked "verified" was shallow-cloned (`git clone --depth 1`) into `/tmp/claude-0/-home-user-lineage-collection-plan/6dff95bd-07a7-5695-ba87-05b72c3b247c/scratchpad/oss/survey/<name>` and read with grep and sed. Nothing was built, installed or run: no `docker compose up`, no Makefile targets, no notebooks executed. "Runs with" therefore means "the repository says it runs with", checked against its compose files, not observed.
- Repositories were treated as untrusted data. Some carry `CLAUDE.md` or `AGENTS.md` files (rp-dbt-rw-fraud-monitor, feast); they were not followed.
- Last-commit dates come from `git log -1` on the shallow clone (whole repository, not the sub-folder).
- Web search: 8 queries used. WebFetch could not reach `alwyndsouza.github.io` or `materialize.com` (blocked by the session's network policy); GitHub clones worked, so the repositories behind them were read directly where the name could be found.
- Line numbers refer to the default branch as cloned on 2026-11-27.

## Hop legend (the plan's slice)

| Code | Hop |
|---|---|
| H1 | A service publishes an event to Kafka, with a schema registry |
| H2 | A stream processor (Flink or Kafka Streams) enriches and renames fields |
| H3 | A sink lands the stream in a lake or warehouse table |
| H4 | A SQL model or dbt builds a fact table |
| H5 | A feature store aggregates a feature |
| H6 | A model is trained on that feature |
| H7 | A serving service calls the model |

Marks used below: **Y** real code for this hop in the repository; **P** partial (a stand-in such as a CSV replayer instead of a service, a different engine, or a hop present but not connected to the others by real data); **N** absent.

---

## Tier A: strongest candidates (verified at source)

### A1. satyazm/Fraud-Detection-using-MLOps

- URL: https://github.com/satyazm/Fraud-Detection-using-MLOps
- Licence: MIT (`LICENSE`). Last commit 2026-11-12. Single maintainer, but active, with CI (`.github/workflows/ci.yml`), tests, architecture decision records (`docs/decisions`) and a model report. Portfolio-style project, not an organisation-backed reference.
- Domain: PaySim synthetic mobile-money transactions (6.36M rows, fraud labels). Not card authorisation, but payments fraud.
- Components and stores: Kafka (`confluentinc/cp-kafka:7.6.1`), PyFlink 2.3 worker, Feast 0.65.0 (Redis online store, file offline store), XGBoost/LightGBM/sklearn with MLflow tracking and registry, FastAPI prediction service, Airflow DAGs (materialisation, weekly retraining, drift report), Prometheus and Grafana.
- Data flow with file paths:
  1. Wire contract: `data/contracts/transaction_schema.json` (JSON Schema draft-07: `step`, `type`, `amount`, `nameOrig`, `oldbalanceOrg`, `newbalanceOrig`, `nameDest`, `oldbalanceDest`, `newbalanceDest`). No schema registry.
  2. Producer replays the PaySim CSV onto topic `transactions`: `src/fraud_detection/streaming/producer.py:1,26`.
  3. PyFlink job reads `transactions` (`src/fraud_detection/streaming/flink_job.py:37,98-147`), per record deserialises, computes features and pushes them to Feast online (`flink_job.py:71-95`).
  4. Feature logic, with an explicit machine-readable source-column list per feature: `src/fraud_detection/features/registry.py:33-100` (for example `orig_balance_error` from `("oldbalanceOrg", "amount", "newbalanceOrig")`), implemented in `src/fraud_detection/features/transformers.py:39-67`.
  5. Feast write path: `src/fraud_detection/features/feast_store.py:78-92` (`write_to_online_store` into feature view `transaction_features`); feature view generated from the registry in `feast_repo/definitions.py:30-53`; config `feast_repo/feature_store.yaml`.
  6. Training with MLflow: `src/fraud_detection/models/training.py:146-167` (logs `feature_version`, `git_commit`, params).
  7. Serving: `src/fraud_detection/api/prediction_service.py:57-75` reads engineered features from Feast online (`feast_store.py:101`) and rebuilds the training row shape (`prediction_service.py:113-140`) before `predict_proba`.
- Hops: H1 P (CSV replayer, JSON, no registry), H2 Y (PyFlink, but row-level transforms, no windows or renames to speak of), H3 P (Feast file offline store only), H4 N, H5 Y (but entity is the transaction, so no aggregation), H6 Y, H7 Y.
- Runs with: `docker-compose.yml` has 8 containers (kafka, kafka-ui, redis, prometheus, redis-exporter, cadvisor, grafana, api); `airflow/docker-compose.yml` adds 4. The PyFlink worker runs on the host (`Makefile` target `flink-worker`, needs a JDK 11/17/21 and Python 3.11). Needs the PaySim CSV from Kaggle (free account); `data/sample` and `data/raw` are empty. No paid services.
- Lineage and telemetry: no OpenLineage or OpenTelemetry configured; metrics via Prometheus. Feast 0.65.0 is new enough to emit OpenLineage natively (added in Feast 0.60.0, `feast/CHANGELOG.md:633`) and to tag MLflow runs with feature references (added in 0.64.0, `feast/CHANGELOG.md:439`), so both could be switched on by configuration; not tried.
- Field-level readability: good. `registry.py` already declares `source_columns` for every feature, which is a ready-made field-level mapping; the contract JSON gives the source schema.

### A2. feast-dev/feast (core library and its examples)

- URL: https://github.com/feast-dev/feast
- Licence: Apache-2.0. Last commit 2026-11-26; release 0.68.0 on 2026-11-10 (`CHANGELOG.md:3`). Very active, organisation-backed.
- What is relevant:
  - Native OpenLineage producer and consumer: `sdk/python/feast/openlineage/` (emitter, mappers, consumer, processor). Feature views are emitted with schema facets (`mappers.py:98-126,362-364,463-480`). Feast also accepts OpenLineage events from other producers and stores `columnLineage` facets (`processor.py:498-507`). Docs: `docs/reference/openlineage.md` (sections on Marquez, dbt, Spark, Airflow producers). Demo: `examples/openlineage-integration/openlineage_demo.py:37-53` (the `openlineage:` block in `feature_store.yaml`).
  - MLflow integration that records feature-to-model lineage: `sdk/python/feast/mlflow_integration/logger.py:80-99` tags training runs with `feast.feature_service`, `feast.feature_views`, `feast.feature_refs`; `logger.py:128` logs the training dataset as an MLflow input; `client.py:150-200` tags registered model versions and prediction runs with the training run and feature service. Docs: `docs/reference/mlflow.md`.
  - End-to-end example (credit risk, not fraud): `examples/credit-risk-end-to-end/` notebooks 01-05: data prep splits the OpenML credit dataset into two parquet sources, feature store deploy, training with `get_historical_features` on nine named features (notebook 03), online serving through the feature server on port 6566 (notebook 04).
- Hops: H5 Y, H6 Y, H7 P (feature server plus a notebook calling the model; no serving service). H1-H4 N.
- Runs with: local Python; credit-risk example needs no containers. No paid services.
- Field-level readability: feature definitions are Python with typed `Field`s; on-demand feature views show derivations in code. The emitted OpenLineage schema facets give feature-view columns, but the producer side does not emit `columnLineage` for its own transformations (no `columnLineage` construction found in `mappers.py`).
- Why it matters: whichever downstream repository is chosen, Feast at 0.64 or later gives the plan an emitter for the feature-store hop and a recorded link from features to models without custom code.

### A3. feast-dev/feast-workshop, module 3 (Kafka plus dbt plus Feast, fraud schema)

- URL: https://github.com/feast-dev/feast-workshop
- Licence: no LICENSE file in the repository. Last commit 2025-11-19. Maintained occasionally; module 3 is marked "still WIP" in its README.
- Domain: PaySim-style fraud transactions (`NAMEORIG`, `AMOUNT`, `isFraud`).
- Data flow with file paths (`module_3_sf`, Snowflake variant; `module_3_db` is the Databricks variant):
  1. `kafka_demo/kafka_demo.py:27-66` replays `data/transactions.parquet` as JSON onto a Kafka topic.
  2. Batch path: dbt incremental model `dbt/feast_demo/models/example/aggregate_transaction_features.sql:4-20` builds `AGGREGATE_TRANSACTION_FEATURES` from `TRANSACTIONS`, with field renames `t.NAMEORIG as USER_ID` and `AVG(AMOUNT) as "7D_AVG_AMT"` over a 7-day lateral window.
  3. Feast sources: `feature_repo/data_sources.py:6-12` (`TRANSACTIONS`), `:14-21` (the dbt output, tagged `dbtModel: models/example/aggregate_transaction_features.sql`), `:23-25` (a `PushSource` named `transactions_7d` backed by the same batch table), `:27-33` (credit scores via an inline SQL query).
  4. Feature views: `feature_repo/features.py:12-34` (`credit_scores_features`, `aggregate_transactions_features` with `USER_ID`, `7D_AVG_AMT`).
  5. Stream path (notebook `feature_repo/module_3.ipynb`): Spark Structured Streaming reads the Kafka topic, computes `avg("amount").alias("7D_AVG_AMT")` grouped by `nameOrig` over a 7-day sliding window, selects `col("nameOrig").alias("USER_ID")`, and calls `store.push("transactions_7d", ...)`.
  6. Training dataset: same notebook calls `get_historical_features` with feature service `model_v2`. No model is fitted in module 3.
- Hops: H1 P, H2 P (Spark, not Flink), H3 P (Snowflake table assumed preloaded), H4 Y (dbt), H5 Y (a real aggregate, computed twice: dbt batch and Spark stream, pushed to one feature view), H6 P (training frame only), H7 P (feature server only).
- Runs with: `module_3_sf/docker-compose.yml` has 6 containers (zookeeper, broker, tx_kafka_events, redis, feature_server, registry) plus Airflow set up by script. Requires a Snowflake account (paid, trial available) or Databricks for `module_3_db`. `module_1` is the fully local variant but uses driver statistics, not fraud.
- Field-level readability: very good. The dbt SQL and the Spark aliasing give explicit renames and an aggregate, and the same feature arrives by two independent paths, which is a strong test case for lineage stitching. The dbt SQL uses Snowflake syntax (`DATEADD`, quoted `"7D_AVG_AMT"`), so a local port to DuckDB or Postgres would need edits.

### A4. lahiruweerasingha/realtime-fraud-detection

- URL: https://github.com/lahiruweerasingha/realtime-fraud-detection
- Licence: MIT. Last commit 2026-10-16. Single maintainer; tests, CI, recorded evidence files (`evidence/`).
- Domain: PaySim (Kaggle) or a bundled synthetic generator (`scripts/make_synthetic_data.py`), so it can run without any account.
- Data flow with file paths:
  1. Batch features in one SQL file: `sql/features.sql:11-42` (window features per `name_dest`, for example `COUNT(1) OVER dest_all AS dest_prior_txn_count`, `LOG1P(t.amount) AS log_amount`, renames `t.txn_type`, `t.step % 24 AS hour_of_day`). Run by Spark: `jobs/build_features.py:19-23` (reads `transactions.parquet`, writes `features.parquet`).
  2. Training with MLflow: `jobs/train.py:338-359` (champion and challenger runs).
  3. Stream: producer replays to Kafka topic `transactions`; PyFlink job `streaming/job.py:66-68` (topics `transactions`, `scores`, `transactions-dlq`), keyed state computes the same features online (`src/fraud/online.py:68-88`), loads the champion model and scores in-stream (`streaming/job.py:130-173`), writes `scores` and InfluxDB.
  4. Parity test that the online features equal the Spark SQL ones: `tests/test_online_parity.py:49`.
- Hops: H1 P, H2 Y (PyFlink with keyed state), H3 P (parquet files, no table format), H4 P (Spark SQL file, not dbt), H5 N, H6 Y, H7 P (scoring inside Flink, no serving service).
- Runs with: `docker-compose.yml`, 13 containers (Spark master, 2 workers, history server, MLflow, runner, Kafka, kafka-init, Flink jobmanager and taskmanager, stream-tools, InfluxDB, Grafana). Everything, including Flink, runs in compose. No paid services.
- Field-level readability: very good for the SQL hop (one file, explicit aliases); the online twin in Python is readable but would need code analysis. No OpenLineage; Spark's OpenLineage listener could be added by configuration (not tried).

### A5. apache/flink-playgrounds

- URL: https://github.com/apache/flink-playgrounds
- Licence: Apache-2.0. Last commit 2026-09-28. Apache project, maintained at a slow pace; images pinned to Flink 1.16.
- Two payment-shaped flows:
  - `table-walkthrough` (transactions to spend report): data generator `docker/data-generator/.../model/Transaction.java:24-30` (`accountId`, `amount`, `timestamp`) serialised as positional CSV in `TransactionSerializer.java:36-40` to topic `transactions` (`DataGenerator.java:34`). Flink Table API job `table-walkthrough/src/main/java/org/apache/flink/playgrounds/spendreport/SpendReport.java:39-50` declares the Kafka source (`account_id`, `amount`, `transaction_time`), `:52-64` the JDBC sink `spend_report` (`account_id`, `log_ts`, `amount`); MySQL DDL `docker/mysql-spend-report-init/create-table.sql:17-22`. Note `report()` at `SpendReport.java:31-33` throws `UnimplementedException`: it is an exercise; the reference answer (hourly sum per account) lives in the Flink documentation, not the repository.
  - `pyflink-walkthrough` (payments by province): generator writes JSON to `payment_msg`; `payment_msg_proccessing.py:38-53` Kafka source (`createTime`, `orderId`, `payAmount`, `payPlatform`, `provinceId`), `:28-30` UDF maps `provinceId` to a name, `:76-80` renames to `province` and `pay_amount` and aggregates into Elasticsearch (`:55-70`).
- Hops: H1 P, H2 Y, H3 P (MySQL or Elasticsearch, not a lake), H4-H7 N.
- Runs with: table-walkthrough 6 containers (jobmanager, taskmanager, kafka, data-generator, mysql, grafana); pyflink-walkthrough 7. No paid services. Risk, not verified: both use `bitnami/kafka:3.9.0`; Bitnami moved most versioned public images to a legacy repository in 2025, so the pull may fail and need an image swap.
- Field-level readability: excellent for the PyFlink case (explicit UDF rename and alias). The CSV positional mapping in the table walkthrough is a useful negative case: field names change between producer and job with no name match, only position.

### A6. debezium/debezium-examples: `openlinage/debezium-flink` and `outbox`

- URL: https://github.com/debezium/debezium-examples (folder name is spelled `openlinage`).
- Licence: Apache-2.0 (`LICENSE.txt`). Last commit 2026-11-26. Organisation-backed, active.
- `openlinage/debezium-flink` (orders, customers, products to shipping orders):
  - Debezium Postgres connector with the OpenLineage SMT: `postgres-connector-openlineage.json:17-23` (`io.debezium.transforms.openlineage.OpenLineage`). Topics `inventory.inventory.orders`, `.customers`, `.products`.
  - Flink DataStream job `flink-job/src/main/java/io/debezium/examples/openlineage/OrderShippingProcessor.java`: sources at `:33,41,49`; field extraction `:278-279` (`purchaser`, `quantity`), `:293-295` (`first_name`, `last_name`, `email`), `:310` (`weight`); derivations `:261` (`totalWeight = productWeight * quantity`), `:341` (`customerName = first + " " + last`); JSON output `:368-369`; sink topic `shipping-orders` `:109`. Flink job also configured for OpenLineage (`flink-job/openlineage.yml`).
  - Runs with: `docker-compose-flink.yaml`, 5 containers (kafka, connect, postgres, jobmanager, taskmanager; two images built locally) plus Marquez (3 containers, started from the Marquez repository). Needs Maven and kcctl on the host. No paid services.
- `outbox` (order service to shipment service): order-service writes an outbox table, Debezium `EventRouter` routes to `${routedByValue}.events` (`outbox/register-postgres.json:11-16`); Kafka Connect exports OpenTelemetry traces to Jaeger (`outbox/docker-compose.yaml:79-83`; README `:136-142`). 8 containers.
- Hops: H1 Y (CDC and outbox are real service-to-topic patterns), H2 Y (Flink joins and derivations), H3-H7 N.
- Lineage and telemetry: OpenLineage from Debezium and from the Flink job at dataset level; OpenTelemetry in the outbox example. Field-level only from the Java code.

### A7. OpenLineage/workshops

- URL: https://github.com/OpenLineage/workshops
- Licence: no LICENSE file in the repository. Last commit 2025-05-09.
- `flink-streaming`: generator writes Avro (`docker/InputEvent.avsc`: `id`, `version`) through Confluent Schema Registry to Kafka; Flink job counts per id (`OutputEvent.avsc` adds `counter`) into Postgres; an Airflow DAG runs Postgres SQL; a second Flink job writes back to Kafka; `openlineage-flink` dependency at `flink-app/build.gradle:69`; Marquez for the graph. 16 containers.
- `flink2/flink-trino-demo`: Flink 2 SQL from Kafka (`user_id`, `price`, `currency`, `log_ts`, computed column `computed-price`) into a Trino table with `TUMBLE` aggregation (`README.md`, DDL and `INSERT INTO trino_output`), Flink 2 native lineage with an unreleased `openlineage-flink` jar, Trino OpenLineage event listener (`docker/trino/openlineage-event-listener.properties`). 9 containers.
- Hops: H1 P (with schema registry in `flink-streaming`), H2 Y, H3 P (Postgres or Trino memory table), H4 P (Airflow SQL), H5-H7 N.
- Value: the only verified repository whose purpose is to emit OpenLineage across Kafka, Flink and a SQL engine. Toy schemas, so weak for field-level semantics. Consistent with the earlier primary-source finding that OpenLineage Flink 2 does not emit column lineage at runtime.

### A8. alwyndsouza/rp-dbt-rw-fraud-monitor

- URL: https://github.com/alwyndsouza/rp-dbt-rw-fraud-monitor
- Licence: none (no LICENSE file, none in README or pyproject), so reuse rights are unclear. Last commit 2026-04-26. Single maintainer.
- Domain: card and banking fraud signals (Australian banking context in `docs/regulatory_context.md`).
- Data flow: Python producer (`producers/models.py:6-28`, `TransactionEvent` with `card_last4`, `merchant_category_code`, `channel`, `device_id`, geo) to Redpanda topics `transactions`, `card_events`, `login_events`, `kyc_profile_events`, `alert_events`. dbt on RisingWave: source DDL `fraud_detection/models/sources/transactions.sql:3-26`; staging view with derived fields `models/staging/stg_transactions.sql:3-26` (`occurred_at::TIMESTAMPTZ`, `txn_hour`, `is_cnp`, `is_high_risk_mcc`); signals such as `models/fraud_signals/mv_velocity_alerts.sql:4-18` (60-second tumble per `account_id`, `card_last4`); risk aggregations including `mv_account_risk_score_realtime.sql`; Grafana dashboards.
- Hops: H1 P (JSON, no registry), H2 Y (RisingWave streaming SQL, not Flink), H3 P (RisingWave state, no lake), H4 Y (dbt, 28 SQL models), H5-H7 N.
- Runs with: `docker-compose.yml`, 7 containers (redpanda, console, risingwave, dbt-run, seed-topics, producer, grafana). No paid services.
- Field-level readability: excellent (dbt SQL with column docs in YAML). The only verified local repository with dbt over a streaming card-fraud feed.

---

## Tier B: useful in part, or with serious caveats (verified at source)

### B1. ejkennedy/Real-Time-Fraud-Detection-MLOps-Platform

- URL: https://github.com/ejkennedy/Real-Time-Fraud-Detection-MLOps-Platform. MIT. Last commit 2026-03-31. Single maintainer.
- Card-shaped schema, the closest to the plan's wording: `services/streaming/src/streaming/schemas/transaction.py:24-36` (`card_id`, `merchant_id`, `amount`, `country_code`, `pos_type`, `mcc`), velocity features `:46-59`, enriched record `:62-86`.
- Flow: Redpanda `transactions-raw` to PyFlink (`services/streaming/src/streaming/job.py:39-40,66-81`, velocity keyed by `card_id`, then a Redis lookup) to `transactions-enriched` (`:83-101`); Feast definitions over synthetic parquet (`services/feature-store/src/feature_store/repo/features.py:39-76`); XGBoost to ONNX; Ray Serve scorer (`services/serving/src/serving/deployments/fraud_scorer.py`).
- Caveats found in the code, which break real lineage between hops:
  - The Flink job's Redis lookup uses a hand-made key `feast:card:{card_id}` (`services/streaming/src/streaming/operators/enrichment.py:47-57`), not Feast's online-store format, so Feast is bypassed.
  - Training uses a synthetic generator, not landed data (`services/training/src/training/pipeline.py:46-47`).
  - The README (`:73,87`) and the job docstring (`job.py:9`) describe an Iceberg offline store, but `job.py` sinks only to Kafka; no Iceberg write exists.
- Hops: H1 P, H2 Y, H3 N, H4 N, H5 P, H6 P, H7 Y. 13 containers (`infra/docker/docker-compose.yml`). No paid services.

### B2. factorhouse/examples `projects/data-lineage-labs` (on factorhouse/factorhouse-local)

- URLs: https://github.com/factorhouse/examples and https://github.com/factorhouse/factorhouse-local. Apache-2.0 (both). Last commits 2026-04-13 and 2026-04-09. Vendor-backed.
- Flow: Kafka Connect datagen source `orders` (Avro, Schema Registry) with a custom OpenLineage SMT (`connectors/orders-source.json`); Flink DataStream supplier stats (`flink-supplier-stats/`, output schema `src/main/avro/SupplierStats.avsc`); Flink Table API Kafka to Iceberg (`flink-iceberg-ingestion/src/main/kotlin/io/factorhouse/demo/TableApp.kt`) with hand-built OpenLineage events carrying schema facets (`openlineage/Integration.kt:101-138`); Spark batch on Iceberg (`spark-supplier-stats/supplier_stats.py`); S3 and Iceberg sink connectors; Marquez.
- Hops: H1 P (with registry), H2 Y, H3 Y (Iceberg on MinIO with Hive Metastore), H4 P (Spark), H5-H7 N.
- Runs with: factorhouse-local compose files: `compose-kpow.yml` 6 containers, `compose-flex.yml` 12, plus a metadata or lineage stack. Kpow and Flex need a licence key; the community editions are free with registration (`lab2_end-to-end.md:44-53`). Heavy.
- Best verified example of H3 (Flink to Iceberg) with OpenLineage, but orders domain and dataset-level only.

### B3. confluentinc/demo-scene `ksql-atm-fraud-detection`

- URL: https://github.com/confluentinc/demo-scene/tree/master/ksql-atm-fraud-detection. Apache-2.0. Repository last commit 2026-10-29, but this demo is pinned to Confluent Platform 5.2.1 (2019).
- Flow: ATM transaction simulator (gess) to topic `atm_txns_gess`; Debezium MySQL CDC of `accounts` (Avro). ksqlDB in `sql/atm_fraud_detection.ksql`: source stream `:1`; self-join within 10 minutes `:15-33` deriving `DISTANCE_BETWEEN_TXN_KM`, `KMH_REQUIRED` (`:21`), `T1_LOCATION` (`:26`); enrichment join `:53-64` with `B.FIRST_NAME + ' ' + B.LAST_NAME AS CUSTOMER_NAME` (`:64`). Sinks to Elasticsearch and Neo4j.
- Hops: H1 P (Avro via registry for CDC), H2 Y (ksqlDB), H3 P, H4-H7 N. 14 containers including Control Center and Neo4j Enterprise (licence acceptance).
- Value: rich, realistic field-level renames and derivations in a fraud setting; old images.

### B4. feast-dev/feast-credit-score-local-tutorial

- URL: https://github.com/feast-dev/feast-credit-score-local-tutorial. Apache-2.0. Last commit 2025-09-21.
- `feature_repo/features.py:17-40` (zipcode features), `:48-72` (credit history), `:74-98` on-demand view `total_debt_due = credit_card_due + mortgage_due + student_loan_due + vehicle_loan_due + loan_amnt` (explicit field derivation); training `credit_model.py:21-37,60-71`; prediction with online features `:96-103`; feature server `app.py:5-14`. Redis is the only container.
- Hops: H5 Y, H6 Y, H7 Y. Small, clean, official; no stream or warehouse.

### B5. logicalclocks/hopsworks-tutorials (fraud_online and the Flink fraud job)

- URL: https://github.com/logicalclocks/hopsworks-tutorials. AGPL-3.0. Last commit 2026-10-05.
- Card-shaped and closest in concept: Avro `integrations/java/flink/src/main/avro/transaction.avsc` (`tid`, `datetime`, `cc_num`, `amount`) to `transaction_agg.avsc` (`num_trans_per_10m`, `avg_amt_per_10m`, `stdev_amt_per_10m`); Flink sliding windows keyed by `cc_num` (`TransactionFraudExample.java:70-72`) written into a feature group (`:75`); training and inference notebooks in `real-time-ai-systems/fraud_online/`.
- Hops: H1 P, H2 Y, H3 P, H5 Y, H6 Y, H7 Y.
- Not runnable locally: the Flink tutorial needs a managed or on-premises Hopsworks cluster (README: at least 8 cores and 16 GiB, "will not work for app.hopsworks.ai"); the notebooks need a Hopsworks account. AGPL.

### B6. mlrun/demo-fraud

- URL: https://github.com/mlrun/demo-fraud. Apache-2.0. Last commit 2026-03-01.
- Transactions and user events ingested into MLRun feature sets with aggregations, training pipeline, real-time serving graph (notebooks 03-05).
- README states the online feature store "is currently not part of the Open Source default deployment", so the real-time hops need the commercial platform. Notebook-only; not verified beyond the README and file list.

### B7. afedulov/fraud-detection-demo (Ververica)

- URL: https://github.com/afedulov/fraud-detection-demo. No LICENSE file (sources carry ASF headers). Last commit 2023-05-12; not maintained.
- Flink dynamic-rules fraud engine: `Transaction.java:39-46` (`transactionId`, `payeeId`, `beneficiaryId`, `paymentAmount`, `paymentType`), topics `livetransactions`, `rules`, `alerts` (`config/Parameters.java:61-66`). Rule-based, no ML. 7 containers on Confluent Platform 5.x images.

---

## Tier C: checked and a weak fit

| Repository | Licence, last commit | What it is | Why weak |
|---|---|---|---|
| confluentinc/cp-demo | Apache-2.0, 2026-11-10 | Wikipedia edits via SSE connector to Kafka (Avro, Schema Registry), ksqlDB (`scripts/ksqlDB/statements.sql`, for example `(length->new - length->old) AS BYTECHANGE`), Kafka Streams, Elasticsearch. 15 containers. | Not payments; needs live Wikimedia feed; Control Center and RBAC are enterprise (trial licence). H1 P, H2 Y, H3 P only. |
| dbt-labs/jaffle-shop | No LICENSE file, 2026-09-15 | dbt staging and marts for orders (`models/staging`, `models/marts`). | README targets dbt Cloud and a cloud warehouse (Postgres also listed); no stream; not fraud. H4 only. |
| dotnet/eShop | MIT, 2026-11-24 | .NET Aspire app (`src/eShop.AppHost/AppHost.cs:8-11`: Redis, RabbitMQ, Postgres); integration events with OpenTelemetry on the bus (`src/EventBusRabbitMQ/RabbitMQEventBus.cs:53,117,148`). | Payment processor is a stub driven by a setting (`src/PaymentProcessor/IntegrationEvents/EventHandling/OrderStatusChangedToStockConfirmedIntegrationEventHandler.cs:21-28`); RabbitMQ not Kafka; no downstream analytics. Overlaps the OpenTelemetry Demo. |
| wuchong/flink-sql-demo | No LICENSE file, 2020-07-28 | Flink 1.11 SQL on e-commerce user behaviour to Elasticsearch. | Stale; not payments. |
| ververica/sql-training | No LICENSE file, archived 2021-11-26 | Flink SQL training. | Archived. |
| MaterializeInc/demos | Apache-2.0, 2025-03-05 | `dbt-jaffle-shop`, `ecommerce`, `ecommerce-redpanda`. | No fraud or feature-store flow; quiet since March 2025. The Materialize "real-time feature store" blog repository could not be located (blog host blocked). |
| risingwavelabs/awesome-stream-processing | Apache-2.0, 2026-06-15 | Many RisingWave demos (`03-solution-demos`, `07-iceberg-demos`, `08-tutorial-demos/dbt`). | No fraud, feature store or model flow found. |
| feast-dev/streaming-tutorial | No LICENSE file, 2022-06-28 | Kafka plus Spark to Feast push (driver stats). | Stale; superseded by feast-workshop module 1. |
| confluentinc/demo-scene `scalable-payment-processing` | Apache-2.0 | Kafka Streams payment state machine (KPay). | Runs from an IDE, no compose; no downstream hops. |

Seen in search results but not verified (not cloned or read): NITESH864/real-time-financial-fraud-detection, Vairavandinesh/real-time-fraud-detection, Sushil2209/Real-Time-Financial-Fraud-Detection-Platform, majlisofai/local-lab-realtime-fraud-detection, janhavi502/fraud-streaming-platform-realtime (Kafka, Spark, Delta, MLflow), k-monolith/Fraud-Detection (scoring inside Flink), hakkache/openlakehouse (Spark, Iceberg, Trino, Kafka, dbt, MLflow), kanersharma/realtime-ecommerce-lakehouse and 1ambda/lakehouse (Kafka, Flink, Iceberg, Trino), getindata/flink-dynamic-cep-demo, Redpanda blog demos (Flink plus MongoDB; TensorFlow plus BigQuery).

---

## (a) Candidates against the slice's hops

Y real code; P partial or stand-in; N absent. "Local" means runnable with Docker Compose or plain Python and no paid account.

| Candidate | H1 svc to topic (+registry) | H2 stream proc | H3 lake/warehouse sink | H4 SQL/dbt | H5 feature store | H6 training | H7 serving | Local, no paid service | Fraud or payments | OpenLineage or OTel |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 satyazm/Fraud-Detection-using-MLOps | P (no registry) | Y PyFlink | P | N | Y Feast (no aggregate) | Y MLflow | Y FastAPI | Yes (Kaggle data download) | Yes | Not configured; Feast 0.65 can emit OL |
| A2 feast-dev/feast | N | N | N | N | Y | Y | P | Yes | No (credit risk) | OL producer and consumer; MLflow lineage tags |
| A3 feast-workshop module 3 | P | P Spark | P | Y dbt | Y aggregate | P | P | No (Snowflake or Databricks) | Yes | Feast OL if upgraded |
| A4 lahiruweerasingha/realtime-fraud-detection | P | Y PyFlink | P | P Spark SQL | N | Y MLflow | P in-stream | Yes | Yes | None |
| A5 apache/flink-playgrounds | P | Y Flink SQL / PyFlink | P MySQL or ES | N | N | N | N | Yes (image risk) | Yes | None |
| A6 debezium-examples (openlinage, outbox) | Y CDC / outbox | Y Flink | N | N | N | N | N | Yes | No (orders) | OL (Debezium, Flink); OTel (outbox) |
| A7 OpenLineage/workshops | P (registry) | Y Flink 1.18 / 2 | P | P | N | N | N | Yes | No | OL throughout |
| A8 rp-dbt-rw-fraud-monitor | P | Y RisingWave | P | Y dbt | N | N | N | Yes | Yes (cards) | None; no licence |
| B1 ejkennedy platform | P | Y PyFlink | N (claimed) | N | P | P (synthetic) | Y Ray Serve | Yes | Yes (cards) | None |
| B2 factorhouse data-lineage-labs | P (registry) | Y Flink | Y Iceberg | P Spark | N | N | N | Free licence keys | No | OL throughout |
| B3 demo-scene ATM fraud | P (registry) | Y ksqlDB | P ES / Neo4j | N | N | N | N | Enterprise images | Yes | None |
| B4 feast credit-score tutorial | N | N | N | N | Y | Y | Y | Yes | No (credit) | Feast OL if upgraded |
| B5 hopsworks-tutorials fraud | P | Y Flink | P | N | Y aggregate | Y | Y | No (Hopsworks cluster) | Yes (cards) | Not checked |
| B6 mlrun/demo-fraud | N | P | N | N | Y | Y | Y | No (online store commercial) | Yes | Not checked |
| B7 afedulov fraud-detection-demo | P | Y Flink rules | N | N | N | N | N | Yes (old images) | Yes | None |

## (b) Recommendation: one complement for the downstream hops

**satyazm/Fraud-Detection-using-MLOps** is the best single complement to the OpenTelemetry Demo for the downstream hops.

Reasons:
- It is the only verified, locally runnable, permissively licensed repository in which the stream processor, Feast, model training and a serving service are connected by real data: the PyFlink job writes the features that the FastAPI service reads from Feast, and the model is trained on the same feature definitions. The card-shaped alternative (ejkennedy) only looks connected (hand-made Redis keys, synthetic training data, Iceberg not implemented), and Hopsworks needs a cluster.
- It is payments fraud, actively maintained (last commit 2026-11-12), MIT, with a written transaction contract and CI.
- It already declares field-level mappings in code (`registry.py` `source_columns`), which gives the plan a ground truth to score collectors against.
- Its pinned Feast 0.65.0 includes the native OpenLineage emitter (Feast 0.60.0 or later) and the MLflow integration (0.64.0 or later), so the feature-store and feature-to-model hops can emit lineage by configuration rather than custom code (not yet tried).

Gaps to accept or fill:
- No warehouse, lakehouse or dbt hop (H3, H4). Best fills: the dbt-plus-Feast pattern from feast-workshop module 3 (fraud schema, same feature built by dbt and by a stream, but Snowflake or Databricks), or rp-dbt-rw-fraud-monitor for a local dbt hop over streaming card data (no licence, so reference only), or the Spark SQL feature file from lahiruweerasingha/realtime-fraud-detection (MIT, local) as a stand-in SQL model.
- Features are per transaction, so the plan's "feature store aggregates a feature" hop is not exercised; feast-workshop module 3's `7D_AVG_AMT` is the verified aggregate example.
- No schema registry; the PyFlink worker runs on the host, not in compose; PaySim must be downloaded from Kaggle.
- Joining it to the OpenTelemetry Demo needs an adapter that maps the Demo's payment or order event onto the PaySim-shaped contract in `data/contracts/transaction_schema.json`; that adapter would itself be a field-level lineage hop.

Runner-up: lahiruweerasingha/realtime-fraud-detection, if a feature store is less important than a SQL feature model and a fully containerised Flink and Spark stack.

## (c) Does any single repository cover most of the slice end to end?

No, not at a verified, runnable, open-licence standard.

- By hop count, Hopsworks (H2, H5, H6, H7 real; card schema) comes closest, but it needs a Hopsworks cluster and is AGPL.
- ejkennedy's platform claims six hops but its hops are not joined by real data, so lineage collected from it would describe code that does not run that way.
- satyazm covers four of the seven hops for real (H2, H5, H6, H7) plus stand-ins for H1 and H3.
- No verified repository combines Flink, dbt and Feast in one runnable flow. The nearest single-repository pattern for dbt into Feast is feast-workshop module 3, which uses Spark and Snowflake.

Practical assembly for the plan: OpenTelemetry Demo for H1; satyazm for H2 and H5 to H7; a dbt model (patterned on feast-workshop module 3 or lahiru's `sql/features.sql`) building the aggregate that Feast reads, for H4; and, if a lake hop is needed, the Flink to Iceberg job from factorhouse data-lineage-labs for H3. Debezium's `openlinage/debezium-flink` and OpenLineage's `workshops` are the reference for wiring OpenLineage across Kafka and Flink, at dataset level only.
