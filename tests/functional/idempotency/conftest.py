import datetime
import hashlib
import json
from collections import namedtuple
from decimal import Decimal
from unittest import mock

import jmespath
import pytest
from botocore import stub
from botocore.config import Config
from jmespath import functions

from aws_lambda_powertools.shared.jmespath_utils import extract_data_from_envelope
from aws_lambda_powertools.shared.json_encoder import Encoder
from aws_lambda_powertools.utilities.idempotency import DynamoDBPersistenceLayer
from aws_lambda_powertools.utilities.idempotency.idempotency import IdempotencyConfig
from aws_lambda_powertools.utilities.validation import envelopes
from tests.functional.utils import load_event

TABLE_NAME = "TEST_TABLE"


def serialize(data):
    return json.dumps(data, sort_keys=True, cls=Encoder)


@pytest.fixture(scope="module")
def config() -> Config:
    return Config(region_name="us-east-1")


@pytest.fixture(scope="module")
def lambda_apigw_event():
    return load_event("apiGatewayProxyV2Event.json")


@pytest.fixture
def lambda_context():
    lambda_context = {
        "function_name": "test-func",
        "memory_limit_in_mb": 128,
        "invoked_function_arn": "arn:aws:lambda:eu-west-1:809313241234:function:test-func",
        "aws_request_id": "52fdfc07-2182-154f-163f-5f0f9a621d72",
    }

    return namedtuple("LambdaContext", lambda_context.keys())(*lambda_context.values())


@pytest.fixture
def timestamp_future():
    return str(int((datetime.datetime.now() + datetime.timedelta(seconds=3600)).timestamp()))


@pytest.fixture
def timestamp_expired():
    now = datetime.datetime.now()
    period = datetime.timedelta(seconds=6400)
    return str(int((now - period).timestamp()))


@pytest.fixture(scope="module")
def lambda_response():
    return {"message": "test", "statusCode": 200, "decimal_val": Decimal("2.5"), "decimal_NaN": Decimal("NaN")}


@pytest.fixture(scope="module")
def serialized_lambda_response(lambda_response):
    return serialize(lambda_response)


@pytest.fixture(scope="module")
def deserialized_lambda_response(lambda_response):
    return json.loads(serialize(lambda_response))


@pytest.fixture
def default_jmespath():
    return "[body, queryStringParameters]"


@pytest.fixture
def expected_params_update_item(serialized_lambda_response, hashed_idempotency_key):
    return {
        "ExpressionAttributeNames": {"#expiry": "expiration", "#response_data": "data", "#status": "status"},
        "ExpressionAttributeValues": {
            ":expiry": stub.ANY,
            ":response_data": serialized_lambda_response,
            ":status": "COMPLETED",
        },
        "Key": {"id": hashed_idempotency_key},
        "TableName": "TEST_TABLE",
        "UpdateExpression": "SET #response_data = :response_data, " "#expiry = :expiry, #status = :status",
    }


@pytest.fixture
def expected_params_update_item_with_validation(
    serialized_lambda_response, hashed_idempotency_key, hashed_validation_key
):
    return {
        "ExpressionAttributeNames": {
            "#expiry": "expiration",
            "#response_data": "data",
            "#status": "status",
            "#validation_key": "validation",
        },
        "ExpressionAttributeValues": {
            ":expiry": stub.ANY,
            ":response_data": serialized_lambda_response,
            ":status": "COMPLETED",
            ":validation_key": hashed_validation_key,
        },
        "Key": {"id": hashed_idempotency_key},
        "TableName": "TEST_TABLE",
        "UpdateExpression": "SET #response_data = :response_data, "
        "#expiry = :expiry, #status = :status, "
        "#validation_key = :validation_key",
    }


@pytest.fixture
def expected_params_put_item(hashed_idempotency_key):
    return {
        "ConditionExpression": "attribute_not_exists(id) OR expiration < :now",
        "ExpressionAttributeValues": {":now": stub.ANY},
        "Item": {"expiration": stub.ANY, "id": hashed_idempotency_key, "status": "INPROGRESS"},
        "TableName": "TEST_TABLE",
    }


@pytest.fixture
def expected_params_put_item_with_validation(hashed_idempotency_key, hashed_validation_key):
    return {
        "ConditionExpression": "attribute_not_exists(id) OR expiration < :now",
        "ExpressionAttributeValues": {":now": stub.ANY},
        "Item": {
            "expiration": stub.ANY,
            "id": hashed_idempotency_key,
            "status": "INPROGRESS",
            "validation": hashed_validation_key,
        },
        "TableName": "TEST_TABLE",
    }


@pytest.fixture
def hashed_idempotency_key(lambda_apigw_event, default_jmespath, lambda_context):
    compiled_jmespath = jmespath.compile(default_jmespath)
    data = compiled_jmespath.search(lambda_apigw_event)
    return f"test-func#{hashlib.md5(serialize(data).encode()).hexdigest()}"


@pytest.fixture
def hashed_idempotency_key_with_envelope(lambda_apigw_event):
    event = extract_data_from_envelope(
        data=lambda_apigw_event, envelope=envelopes.API_GATEWAY_HTTP, jmespath_options={}
    )
    return f"test-func#{hashlib.md5(serialize(event).encode()).hexdigest()}"


@pytest.fixture
def hashed_validation_key(lambda_apigw_event):
    return hashlib.md5(serialize(lambda_apigw_event["requestContext"]).encode()).hexdigest()


@pytest.fixture
def persistence_store(config):
    return DynamoDBPersistenceLayer(table_name=TABLE_NAME, boto_config=config)


@pytest.fixture
def idempotency_config(config, request, default_jmespath):
    return IdempotencyConfig(
        event_key_jmespath=request.param.get("event_key_jmespath") or default_jmespath,
        use_local_cache=request.param["use_local_cache"],
    )


@pytest.fixture
def config_without_jmespath(config, request):
    return IdempotencyConfig(use_local_cache=request.param["use_local_cache"])


@pytest.fixture
def config_with_validation(config, request, default_jmespath):
    return IdempotencyConfig(
        event_key_jmespath=default_jmespath,
        use_local_cache=request.param,
        payload_validation_jmespath="requestContext",
    )


@pytest.fixture
def config_with_jmespath_options(config, request):
    class CustomFunctions(functions.Functions):
        @functions.signature({"types": ["string"]})
        def _func_echo_decoder(self, value):
            return value

    return IdempotencyConfig(
        use_local_cache=False,
        event_key_jmespath=request.param,
        jmespath_options={"custom_functions": CustomFunctions()},
    )


@pytest.fixture
def mock_function():
    return mock.MagicMock()
