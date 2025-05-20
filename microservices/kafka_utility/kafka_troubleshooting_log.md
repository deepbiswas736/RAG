# Kafka Connection Troubleshooting Log

## 1. Problem Description

The `kafka_utility` service is experiencing connection issues with the Kafka broker (`confluentinc/cp-kafka:7.6.1`, Apache Kafka 3.6.1).
Initial errors indicated `IncompatibleBrokerVersion` (specifically `Kafka broker does not support the 'MetadataRequest_v0' Kafka protocol`), suggesting a mismatch between client library versions (`kafka-python`, `aiokafka`) or the `api_version` parameter used by `AIOKafkaAdminClient` and the broker's capabilities.
A subsequent `TypeError` occurred when `api_version` was set to `None` in an attempt to force auto-detection.

## 2. Environment

*   **Kafka Broker:** `confluentinc/cp-kafka:7.6.1` (Apache Kafka 3.6.1) - defined in `e:\code\experimental\RAG\docker-compose.yml`
*   **`kafka-python`:** Initial: `2.0.2`, Current: `>=2.0.2`
*   **`aiokafka`:** Initial: `0.10.0`, Current: `>=0.11.0`
*   **Affected Files:**
    *   `e:\code\experimental\RAG\microservices\kafka_utility\requirements.txt`
    *   `e:\code\experimental\RAG\microservices\kafka_utility\app\application\services\topic_management_service.py`
    *   `e:\code\experimental\RAG\microservices\kafka_utility\app\application\services\kafka_health_service.py`

## 3. Chronological Log of Attempts

| # | Date       | Action                                                                                                                               | File(s) Modified                                                                                                                                                                                             | `api_version` (TMS) | `api_version` (KHS) | `kafka-python` | `aiokafka` | Outcome / Error                                                                                                                               |
|---|------------|--------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------|---------------------|----------------|------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | 2025-05-19 | Initial state                                                                                                                        | `requirements.txt`                                                                                                                                                                                           | `auto` (default)    | `auto` (default)    | `2.0.2`        | `0.10.0`   | `IncompatibleBrokerVersion` for `MetadataRequest_v0`                                                                                            |
| 2 | 2025-05-19 | Updated `kafka-python` to `>=2.0.2`                                                                                                    | `requirements.txt`                                                                                                                                                                                           | `auto`              | `auto`              | `>=2.0.2`      | `0.10.0`   | `IncompatibleBrokerVersion` for `MetadataRequest_v0`                                                                                            |
| 3 | 2025-05-19 | Set `api_version="auto"` explicitly in TMS & KHS                                                                                       | `topic_management_service.py`, `kafka_health_service.py`                                                                                                                                                       | `"auto"`            | `"auto"`            | `>=2.0.2`      | `0.10.0`   | `IncompatibleBrokerVersion` for `MetadataRequest_v0` (TMS)                                                                                      |
| 4 | 2025-05-19 | Set `api_version="0.9"` in TMS                                                                                                         | `topic_management_service.py`                                                                                                                                                                                | `"0.9"`             | `"auto"`            | `>=2.0.2`      | `0.10.0`   | `IncompatibleBrokerVersion` for `MetadataRequest_v0` (TMS)                                                                                      |
| 5 | 2025-05-19 | Set `api_version="latest"` in TMS & KHS                                                                                                | `topic_management_service.py`, `kafka_health_service.py`                                                                                                                                                       | `"latest"`          | `"latest"`          | `>=2.0.2`      | `0.10.0`   | `Kafka health check error: Invalid version: 'latest'` (KHS)                                                                                     |
| 6 | 2025-05-19 | Set `api_version="auto"` in KHS (revert from "latest")                                                                                 | `kafka_health_service.py`                                                                                                                                                                                    | `"latest"`          | `"auto"`            | `>=2.0.2`      | `0.10.0`   | Error likely persisted in TMS due to "latest"                                                                                                   |
| 7 | 2025-05-19 | Set `api_version="2.0.0"` in TMS                                                                                                       | `topic_management_service.py`                                                                                                                                                                                | `"2.0.0"`           | `"auto"`            | `>=2.0.2`      | `0.10.0`   | `IncompatibleBrokerVersion` for `MetadataRequest_v0` (TMS)                                                                                      |
| 8 | 2025-05-20 | Updated `aiokafka` to `>=0.11.0`                                                                                                       | `requirements.txt`                                                                                                                                                                                           | `"2.0.0"`           | `"auto"`            | `>=2.0.2`      | `>=0.11.0` | `IncompatibleBrokerVersion` for `MetadataRequest_v0` (TMS)                                                                                      |
| 9 | 2025-05-20 | Set `api_version="auto"` in TMS (revert from "2.0.0")                                                                                  | `topic_management_service.py`                                                                                                                                                                                | `"auto"`            | `"auto"`            | `>=2.0.2`      | `>=0.11.0` | `IncompatibleBrokerVersion` for `MetadataRequest_v0` (TMS)                                                                                      |
| 10| 2025-05-20 | Set `api_version="2.8.0"` in TMS                                                                                                       | `topic_management_service.py`                                                                                                                                                                                | `"2.8.0"`           | `"auto"`            | `>=2.0.2`      | `>=0.11.0` | `IncompatibleBrokerVersion` for `MetadataRequest_v0` (TMS)                                                                                      |
| 11| 2025-05-20 | Set `api_version="3.6.0"` in TMS                                                                                                       | `topic_management_service.py`                                                                                                                                                                                | `"3.6.0"`           | `"auto"`            | `>=2.0.2`      | `>=0.11.0` | `Error ensuring topic 'document_events' exists: 3.6.0` (TMS) - `api_version` string likely misused.                                         |
| 12| 2025-05-20 | Set `api_version=None` in TMS                                                                                                          | `topic_management_service.py`                                                                                                                                                                                | `None`              | `"auto"`            | `>=2.0.2`      | `>=0.11.0` | `TypeError: expected string or bytes-like object, got 'NoneType'` (TMS)                                                                       |
| 13| 2025-05-20 | Set `api_version="auto"` in TMS (revert from `None`). Rebuilt and checked logs. | `topic_management_service.py`                                                                                                                                                                                | `"auto"`            | `"auto"`            | `>=2.0.2`      | `>=0.11.0` | `IncompatibleBrokerVersion` for `MetadataRequest_v0` (TMS) - Error persists. |
| 14| 2025-05-20 | Set `api_version="3.6"` in TMS & KHS. (Broker is 3.6.1)                                                                                | `topic_management_service.py`, `kafka_health_service.py`                                                                                                                                                       | `"3.6"`             | `"3.6"`             | `>=2.0.2`      | `>=0.11.0` | `Kafka health check error: 3.6` (KHS). `aiokafka` likely misinterprets this string. |
| 15| 2025-05-20 | Revert `api_version="auto"` in TMS & KHS. Add explicit logging for `bootstrap_servers`. | `topic_management_service.py`, `kafka_health_service.py`                                                                                                                                                       | `"auto"`            | `"auto"`            | `>=2.0.2`      | `>=0.11.0` | `IncompatibleBrokerVersion` for `MetadataRequest_v0` (KHS). Logging for `bootstrap_servers` was incorrect (showed literal string). |
| 16| 2025-05-20 | Correct logging for `bootstrap_servers` in TMS & KHS. Keep `api_version="auto"`.      | `topic_management_service.py`, `kafka_health_service.py`                                                                                                                                                       | `"auto"`            | `"auto"`            | `>=2.0.2`      | `>=0.11.0` | `IncompatibleBrokerVersion` for `MetadataRequest_v0` (KHS). `bootstrap_servers` confirmed as `kafka:29092`. Broker version is Confluent 7.6.1 (Kafka ~7.6.1), not 3.6.1. |
| 17| 2025-05-20 | Set `api_version="7.6"` in TMS & KHS. Verified `KAFKA_ADVERTISED_LISTENERS`.         | `topic_management_service.py`, `kafka_health_service.py`, `docker-compose.yml`                                                                                                                               | `"7.6"`             | `"7.6"`             | `>=2.0.2`      | `>=0.11.0` | `Kafka health check error: 7.6` (KHS). `aiokafka` likely misinterprets this string. `KAFKA_ADVERTISED_LISTENERS` is `PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092`. |
| 18| 2025-05-20 | Set `api_version=(7,6,0)` in TMS & KHS (experimental, as aiokafka docs imply string). | `topic_management_service.py`, `kafka_health_service.py`                                                                                                                                                       | `(7,6,0)`           | `(7,6,0)`           | `>=2.0.2`      | `>=0.11.0` | Assumed `TypeError` or persistent `IncompatibleBrokerVersion` (Log check failed due to incorrect path). `aiokafka` likely expects a string. |
| 19| 2025-05-21 | Revert `api_version="auto"` in TMS & KHS.                                            | `topic_management_service.py`, `kafka_health_service.py`                                                                                                                                                       | `"auto"`            | `"auto"`            | `>=2.0.2`      | `>=0.11.0` | Pending log check.                                                                                                                              |

*TMS = TopicManagementService*
*KHS = KafkaHealthService*

## 4. Current Status (as of 2025-05-20)

*   **`kafka-python`:** `>=2.0.2`
*   **`aiokafka`:** `>=0.11.0`
*   **`topic_management_service.py` -> `AIOKafkaAdminClient` -> `api_version`:** `(7,6,0)` (Attempting tuple)
*   **`kafka_health_service.py` -> `AIOKafkaAdminClient` -> `api_version`:** `(7,6,0)` (Attempting tuple)

**Correction:** The Kafka broker image is `confluentinc/cp-kafka:7.6.1`, which means the Kafka version is approximately 7.6.1, **not** 3.6.1 as previously assumed.

**Next Step:**
1.  **Action:** Modify `api_version` to the tuple `(7,6,0)` in `app/application/services/topic_management_service.py` and `app/application/services/kafka_health_service.py`.
2.  **Build & Run:** Rebuild and restart the `kafka_utility` service: `docker-compose up -d --build kafka_utility`
3.  **Verify:** Check the logs: `docker-compose logs kafka_utility`. Note the outcome for `api_version=(7,6,0)`.
4.  **Contingency:** If this fails (e.g., `TypeError` if `aiokafka` strictly expects a string, or if the `IncompatibleBrokerVersion` persists):
    *   Revert to `api_version="auto"`.
    *   Focus on deeper `aiokafka` / `kafka-python` behavior. It's possible `"auto"` *should* work and there's a more subtle issue (e.g. specific feature negotiation failing, or an issue within the `kafka-python` C bindings if `librdkafka` is involved indirectly, though less likely for AdminClient initially).
    *   Consider testing with a simpler `kafka-python` script directly inside the `kafka_utility` container to isolate the issue from `aiokafka` if necessary)

## 4. Current Status (as of 2025-05-21)

*   **`kafka-python`:** `>=2.0.2`
*   **`aiokafka`:** `>=0.11.0`
*   **`topic_management_service.py` -> `AIOKafkaAdminClient` -> `api_version`:** `"auto"` (Reverted)
*   **`kafka_health_service.py` -> `AIOKafkaAdminClient` -> `api_version`:** `"auto"` (Reverted)

**Correction:** The Kafka broker image is `confluentinc/cp-kafka:7.6.1`, which means the Kafka version is approximately 7.6.1, **not** 3.6.1 as previously assumed.

**Next Step:**
1.  **Action:** Revert `api_version` to `\"auto\"` in `app/application/services/topic_management_service.py` and `app/application/services/kafka_health_service.py`.
2.  **Build & Run:** Rebuild and restart the `kafka_utility` service: `docker-compose -f e:/code/experimental/RAG/docker-compose.yml up -d --build kafka_utility` (using absolute path for compose file).
3.  **Verify:** Check the logs: `docker-compose -f e:/code/experimental/RAG/docker-compose.yml logs kafka_utility`. Note the outcome for `api_version=\"auto\"`.
4.  **Contingency:** If `IncompatibleBrokerVersion` for `MetadataRequest_v0` persists:
    *   The core issue is why the client is attempting `MetadataRequest_v0` with a Kafka 7.6.1 broker when `api_version=\"auto\"`.

## 5. Resolution (2025-05-21)

The `IncompatibleBrokerVersion` error (specifically `Kafka broker does not support the 'MetadataRequest_v0' Kafka protocol`) was resolved by a combination of library updates and correct `api_version` configuration for `AIOKafkaAdminClient`.

**Key Steps & Findings:**

1.  **Library Updates:**
    *   `kafka-python` was confirmed to be `>=2.0.2`.
    *   `aiokafka` was updated to `>=0.11.0`.
    *   Missing dependencies `uvicorn>=0.20.0` and `fastapi
