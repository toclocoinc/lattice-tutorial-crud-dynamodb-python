# Part 3: read, add, delete and PATCH products.
#
#   GET     /              every product
#   POST    /              add the product in the JSON body
#   PATCH   /?sku=XXX      change the fields in the JSON body on one product
#   DELETE  /?sku=XXX      delete one product
import json
import os
import time
from datetime import date
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

TABLE = os.environ.get('TABLE_NAME', 'Products')
EDITABLE = ('name', 'category', 'quantity', 'price')
table = boto3.resource('dynamodb').Table(TABLE)


def decimalise(value):
    """Turn DynamoDB's Decimal numbers into plain int/float for JSON.

    DynamoDB has exactly one numeric type, and boto3 always hands it back
    as decimal.Decimal, which json.dumps refuses to serialise on its own.
    A Decimal with no fractional part becomes an int; anything else
    becomes a float.
    """
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, list):
        return [decimalise(v) for v in value]
    if isinstance(value, dict):
        return {key: decimalise(v) for key, v in value.items()}
    return value


def to_decimal(value):
    """Coerce an incoming JSON number (or numeric string) to Decimal."""
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(0)


def new_sku():
    digits = '0123456789abcdefghijklmnopqrstuvwxyz'
    n = int(time.time() * 1000)
    out = []
    while n:
        n, r = divmod(n, 36)
        out.append(digits[r])
    return 'SKU-' + ''.join(reversed(out)).upper()


def today():
    return date.today().isoformat()


def response(status_code, body=None):
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': '' if body is None else json.dumps(body),
    }


def parse_body(event):
    try:
        return json.loads(event.get('body') or '{}')
    except json.JSONDecodeError:
        return None


def lambda_handler(event, context):
    method = (event.get('requestContext') or {}).get('http', {}).get('method', 'GET')
    query = event.get('queryStringParameters') or {}

    if method == 'GET':
        items = []
        start_key = None
        while True:
            kwargs = {'ExclusiveStartKey': start_key} if start_key else {}
            page = table.scan(**kwargs)
            items.extend(page.get('Items', []))
            start_key = page.get('LastEvaluatedKey')
            if not start_key:
                break
        return response(200, {'items': decimalise(items), 'count': len(items)})

    if method == 'POST':
        item = parse_body(event)
        if item is None:
            return response(400, {'error': 'Body must be JSON'})
        if not item.get('name'):
            return response(400, {'error': 'A product needs a name'})
        if not item.get('sku'):
            item['sku'] = new_sku()
        item['quantity'] = to_decimal(item.get('quantity'))
        item['price'] = to_decimal(item.get('price'))
        item['updated'] = today()
        try:
            table.put_item(Item=item, ConditionExpression='attribute_not_exists(sku)')
        except ClientError as err:
            if err.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return response(409, {'error': 'That sku already exists'})
            raise
        return response(201, decimalise(item))

    if method == 'PATCH':
        sku = query.get('sku')
        changes = parse_body(event)
        if not sku:
            return response(400, {'error': 'sku is required'})
        if changes is None:
            return response(400, {'error': 'Body must be JSON'})
        # Only the fields we allow, each as a SET clause. Numbers arrive as
        # numbers from the grid, but coerce anyway: a PATCH is a public door.
        names, values, sets = {}, {}, []
        for field in EDITABLE:
            if field not in changes:
                continue
            v = to_decimal(changes[field]) if field in ('quantity', 'price') else str(changes[field])
            names['#' + field] = field
            values[':' + field] = v
            sets.append(f'#{field} = :{field}')
        if not sets:
            return response(400, {'error': 'Nothing to change'})
        names['#updated'] = 'updated'
        values[':updated'] = today()
        sets.append('#updated = :updated')
        try:
            out = table.update_item(
                Key={'sku': sku},
                UpdateExpression='SET ' + ', '.join(sets),
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ConditionExpression='attribute_exists(sku)',  # never create by accident
                ReturnValues='ALL_NEW',
            )
        except ClientError as err:
            if err.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return response(404, {'error': 'No such product'})
            raise
        return response(200, decimalise(out.get('Attributes', {})))

    if method == 'DELETE':
        sku = query.get('sku')
        if not sku:
            return response(400, {'error': 'sku is required'})
        table.delete_item(Key={'sku': sku})
        return response(204)

    return response(405, {'error': f'Method {method} is not supported'})
