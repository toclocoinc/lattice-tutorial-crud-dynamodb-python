"""Unit tests for part 1's Lambda.

Runs with ``python3 -m unittest discover`` (or ``-m unittest`` directly)
against a stubbed DynamoDB client from botocore — no network calls, no AWS
credentials needed.
"""
import json
import os
import unittest
from decimal import Decimal

os.environ.setdefault('AWS_DEFAULT_REGION', 'eu-west-2')
os.environ.setdefault('TABLE_NAME', 'Products')

from boto3.dynamodb.types import TypeSerializer  # noqa: E402
from botocore.stub import Stubber  # noqa: E402

import lambda_function as lf  # noqa: E402

_serializer = TypeSerializer()


def av(item):
    """Wrap a plain dict as DynamoDB's wire-format AttributeValue map.

    The Stubber sits under the resource's Python<->DynamoDB type
    translation, so responses must be given in the service's own format
    (``{'sku': {'S': 'A-1'}}``), not the plain dict the resource API
    returns to callers.
    """
    return {k: _serializer.serialize(v) for k, v in item.items()}


def http_event(method='GET'):
    return {'requestContext': {'http': {'method': method}}}


class LambdaFunctionTest(unittest.TestCase):
    def setUp(self):
        self.stubber = Stubber(lf.table.meta.client)
        self.stubber.activate()
        self.addCleanup(self.stubber.deactivate)
        self.addCleanup(self.stubber.assert_no_pending_responses)

    def test_get_returns_items_and_count(self):
        self.stubber.add_response(
            'scan',
            {'Items': [av({'sku': 'A-1', 'name': 'Widget'})]},
            {'TableName': 'Products'},
        )
        result = lf.lambda_handler(http_event(), None)
        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['items'][0]['sku'], 'A-1')

    def test_decimal_quantity_becomes_int_and_price_becomes_float(self):
        self.stubber.add_response(
            'scan',
            {'Items': [av({'sku': 'A-1', 'quantity': Decimal('5'), 'price': Decimal('9.99')})]},
            {'TableName': 'Products'},
        )
        result = lf.lambda_handler(http_event(), None)
        body = json.loads(result['body'])
        item = body['items'][0]
        self.assertEqual(item['quantity'], 5)
        self.assertIsInstance(item['quantity'], int)
        self.assertEqual(item['price'], 9.99)
        self.assertIsInstance(item['price'], float)

    def test_scan_paginates_until_no_last_evaluated_key(self):
        self.stubber.add_response(
            'scan',
            {'Items': [av({'sku': 'A-1'})], 'LastEvaluatedKey': av({'sku': 'A-1'})},
            {'TableName': 'Products'},
        )
        self.stubber.add_response(
            'scan',
            {'Items': [av({'sku': 'A-2'})]},
            {'TableName': 'Products', 'ExclusiveStartKey': {'sku': 'A-1'}},
        )
        result = lf.lambda_handler(http_event(), None)
        body = json.loads(result['body'])
        self.assertEqual(body['count'], 2)
        self.assertEqual([i['sku'] for i in body['items']], ['A-1', 'A-2'])

    def test_response_headers_are_content_type_only(self):
        # CORS is configured on the Function URL itself (the Console step),
        # not in code, so the only header the function sets is the content
        # type; this is the same contract the Node Lambda uses.
        self.stubber.add_response('scan', {'Items': []}, {'TableName': 'Products'})
        result = lf.lambda_handler(http_event(), None)
        self.assertEqual(result['headers'], {'Content-Type': 'application/json'})

    def test_missing_http_method_defaults_to_get(self):
        self.stubber.add_response('scan', {'Items': []}, {'TableName': 'Products'})
        result = lf.lambda_handler({}, None)
        self.assertEqual(result['statusCode'], 200)


if __name__ == '__main__':
    unittest.main()
