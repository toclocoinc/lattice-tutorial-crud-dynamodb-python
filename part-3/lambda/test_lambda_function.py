"""Unit tests for part 3's Lambda: GET, POST, PATCH, DELETE.

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


class StubbedTest(unittest.TestCase):
    def setUp(self):
        self.stubber = Stubber(lf.table.meta.client)
        self.stubber.activate()
        self.addCleanup(self.stubber.deactivate)
        self.addCleanup(self.stubber.assert_no_pending_responses)


class GetTest(StubbedTest):
    def test_get_returns_items_and_decimals_convert(self):
        self.stubber.add_response(
            'scan',
            {'Items': [av({'sku': 'A-1', 'quantity': Decimal('5'), 'price': Decimal('9.99')})]},
            {'TableName': 'Products'},
        )
        result = lf.lambda_handler(http_event('GET'), None)
        body = json.loads(result['body'])
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
        self.assertEqual(json.loads(result['body'])['count'], 2)

    def test_response_headers_are_content_type_only(self):
        self.stubber.add_response('scan', {'Items': []}, {'TableName': 'Products'})
        result = lf.lambda_handler(http_event('GET'), None)
        self.assertEqual(result['headers'], {'Content-Type': 'application/json'})


class PostTest(StubbedTest):
    def test_post_assigns_sku_and_converts_decimal_back(self):
        self.stubber.add_response('put_item', {}, {
            'TableName': 'Products',
            'Item': ANY,
            'ConditionExpression': 'attribute_not_exists(sku)',
        })
        result = lf.lambda_handler(
            http_event('POST', body={'name': 'Widget', 'quantity': 3, 'price': 4.5}),
            None,
        )
        self.assertEqual(result['statusCode'], 201)
        body = json.loads(result['body'])
        self.assertTrue(body['sku'].startswith('SKU-'))
        self.assertIsInstance(body['quantity'], int)
        self.assertIsInstance(body['price'], float)

    def test_post_conditional_write_conflict_returns_409(self):
        self.stubber.add_client_error(
            'put_item',
            service_error_code='ConditionalCheckFailedException',
            service_message='The conditional request failed',
            http_status_code=400,
        )
        result = lf.lambda_handler(
            http_event('POST', body={'sku': 'A-1', 'name': 'Widget'}),
            None,
        )
        self.assertEqual(result['statusCode'], 409)


class PatchTest(StubbedTest):
    def test_patch_updates_allowed_fields_and_returns_new_item(self):
        self.stubber.add_response(
            'update_item',
            {'Attributes': av({'sku': 'A-1', 'name': 'Widget', 'quantity': Decimal('9'), 'price': Decimal('4.50'), 'updated': lf.today()})},
            {
                'TableName': 'Products',
                'Key': {'sku': 'A-1'},
                'UpdateExpression': ANY,
                'ExpressionAttributeNames': ANY,
                'ExpressionAttributeValues': ANY,
                'ConditionExpression': 'attribute_exists(sku)',
                'ReturnValues': 'ALL_NEW',
            },
        )
        result = lf.lambda_handler(
            http_event('PATCH', body={'quantity': 9}, query={'sku': 'A-1'}),
            None,
        )
        self.assertEqual(result['statusCode'], 200)
        body = json.loads(result['body'])
        self.assertEqual(body['quantity'], 9)
        self.assertIsInstance(body['quantity'], int)

    def test_patch_ignores_fields_outside_the_allow_list(self):
        # 'sku' itself is not in EDITABLE, so a body that only tries to
        # change it has nothing to apply.
        result = lf.lambda_handler(
            http_event('PATCH', body={'sku': 'NEW-SKU'}, query={'sku': 'A-1'}),
            None,
        )
        self.assertEqual(result['statusCode'], 400)
        self.assertEqual(json.loads(result['body'])['error'], 'Nothing to change')

    def test_patch_without_sku_query_param_is_rejected(self):
        result = lf.lambda_handler(http_event('PATCH', body={'quantity': 1}, query={}), None)
        self.assertEqual(result['statusCode'], 400)

    def test_patch_conditional_check_failure_returns_404(self):
        self.stubber.add_client_error(
            'update_item',
            service_error_code='ConditionalCheckFailedException',
            service_message='The conditional request failed',
            http_status_code=400,
        )
        result = lf.lambda_handler(
            http_event('PATCH', body={'quantity': 1}, query={'sku': 'NO-SUCH'}),
            None,
        )
        self.assertEqual(result['statusCode'], 404)
        self.assertEqual(json.loads(result['body'])['error'], 'No such product')


class DeleteTest(StubbedTest):
    def test_delete_removes_item_by_sku(self):
        self.stubber.add_response('delete_item', {}, {
            'TableName': 'Products',
            'Key': {'sku': 'A-1'},
        })
        result = lf.lambda_handler(http_event('DELETE', query={'sku': 'A-1'}), None)
        self.assertEqual(result['statusCode'], 204)


class MethodNotSupportedTest(unittest.TestCase):
    def test_unsupported_method_returns_405(self):
        result = lf.lambda_handler(http_event('PUT'), None)
        self.assertEqual(result['statusCode'], 405)


if __name__ == '__main__':
    unittest.main()
