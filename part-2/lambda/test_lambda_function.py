"""Unit tests for part 2's Lambda: GET, POST, DELETE.

Runs with ``python3 -m unittest discover`` against a stubbed DynamoDB
client from botocore — no network calls, no AWS credentials needed.
"""
import json
import os
import unittest
from decimal import Decimal

os.environ.setdefault('AWS_DEFAULT_REGION', 'eu-west-2')
os.environ.setdefault('TABLE_NAME', 'Products')

from boto3.dynamodb.types import TypeSerializer  # noqa: E402
from botocore.stub import ANY, Stubber  # noqa: E402

import lambda_function as lf  # noqa: E402

_serializer = TypeSerializer()


def av(item):
    """Wrap a plain dict as DynamoDB's wire-format AttributeValue map."""
    return {k: _serializer.serialize(v) for k, v in item.items()}


def http_event(method, body=None, query=None):
    event = {'requestContext': {'http': {'method': method}}}
    if body is not None:
        event['body'] = json.dumps(body)
    if query is not None:
        event['queryStringParameters'] = query
    return event


class GetTest(unittest.TestCase):
    def setUp(self):
        self.stubber = Stubber(lf.table.meta.client)
        self.stubber.activate()
        self.addCleanup(self.stubber.deactivate)
        self.addCleanup(self.stubber.assert_no_pending_responses)

    def test_get_returns_items_and_decimals_convert(self):
        self.stubber.add_response(
            'scan',
            {'Items': [av({'sku': 'A-1', 'quantity': Decimal('5'), 'price': Decimal('9.99')})]},
            {'TableName': 'Products'},
        )
        result = lf.lambda_handler(http_event('GET'), None)
        body = json.loads(result['body'])
        self.assertEqual(body['count'], 1)
        item = body['items'][0]
        self.assertEqual(item['quantity'], 5)
        self.assertIsInstance(item['quantity'], int)
        self.assertEqual(item['price'], 9.99)
        self.assertIsInstance(item['price'], float)

    def test_get_paginates(self):
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
        result = lf.lambda_handler(http_event('GET'), None)
        body = json.loads(result['body'])
        self.assertEqual(body['count'], 2)

    def test_response_headers_are_content_type_only(self):
        self.stubber.add_response('scan', {'Items': []}, {'TableName': 'Products'})
        result = lf.lambda_handler(http_event('GET'), None)
        self.assertEqual(result['headers'], {'Content-Type': 'application/json'})


class PostTest(unittest.TestCase):
    def setUp(self):
        self.stubber = Stubber(lf.table.meta.client)
        self.stubber.activate()
        self.addCleanup(self.stubber.deactivate)
        self.addCleanup(self.stubber.assert_no_pending_responses)

    def test_post_assigns_sku_and_writes_decimal(self):
        self.stubber.add_response('put_item', {}, {
            'TableName': 'Products',
            'Item': ANY,
            'ConditionExpression': 'attribute_not_exists(sku)',
        })
        result = lf.lambda_handler(
            http_event('POST', body={'name': 'Widget', 'category': 'Office', 'quantity': 3, 'price': 4.5}),
            None,
        )
        self.assertEqual(result['statusCode'], 201)
        body = json.loads(result['body'])
        self.assertTrue(body['sku'].startswith('SKU-'))
        self.assertEqual(body['quantity'], 3)
        self.assertIsInstance(body['quantity'], int)
        self.assertEqual(body['price'], 4.5)
        self.assertIn('updated', body)

    def test_post_without_name_is_rejected_before_any_write(self):
        result = lf.lambda_handler(http_event('POST', body={'category': 'Office'}), None)
        self.assertEqual(result['statusCode'], 400)
        self.assertEqual(json.loads(result['body'])['error'], 'A product needs a name')

    def test_post_conditional_write_conflict_returns_409(self):
        self.stubber.add_client_error(
            'put_item',
            service_error_code='ConditionalCheckFailedException',
            service_message='The conditional request failed',
            http_status_code=400,
        )
        result = lf.lambda_handler(
            http_event('POST', body={'sku': 'A-1', 'name': 'Widget', 'quantity': 1, 'price': 1}),
            None,
        )
        self.assertEqual(result['statusCode'], 409)
        self.assertEqual(json.loads(result['body'])['error'], 'That sku already exists')

    def test_post_with_invalid_json_body_is_rejected(self):
        event = {'requestContext': {'http': {'method': 'POST'}}, 'body': 'not json'}
        result = lf.lambda_handler(event, None)
        self.assertEqual(result['statusCode'], 400)


class DeleteTest(unittest.TestCase):
    def setUp(self):
        self.stubber = Stubber(lf.table.meta.client)
        self.stubber.activate()
        self.addCleanup(self.stubber.deactivate)
        self.addCleanup(self.stubber.assert_no_pending_responses)

    def test_delete_removes_item_by_sku(self):
        self.stubber.add_response('delete_item', {}, {
            'TableName': 'Products',
            'Key': {'sku': 'A-1'},
        })
        result = lf.lambda_handler(http_event('DELETE', query={'sku': 'A-1'}), None)
        self.assertEqual(result['statusCode'], 204)

    def test_delete_without_sku_is_rejected_before_any_write(self):
        result = lf.lambda_handler(http_event('DELETE', query={}), None)
        self.assertEqual(result['statusCode'], 400)


class MethodNotSupportedTest(unittest.TestCase):
    def test_unsupported_method_returns_405(self):
        result = lf.lambda_handler(http_event('PUT'), None)
        self.assertEqual(result['statusCode'], 405)


if __name__ == '__main__':
    unittest.main()
