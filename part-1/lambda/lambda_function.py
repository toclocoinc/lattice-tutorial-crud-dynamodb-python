# Part 1: read every product from DynamoDB and return it as JSON.
#
# Runs on the Python 3.13 Lambda runtime, which ships boto3, so there is
# nothing to install. The table name comes from an environment variable so
# the same code works whatever you called the table.
import json
import os
from decimal import Decimal

import boto3

TABLE = os.environ.get('TABLE_NAME', 'Products')
table = boto3.resource('dynamodb').Table(TABLE)


def decimalise(value):
    """Turn DynamoDB's Decimal numbers into plain int/float for JSON.

    DynamoDB has exactly one numeric type, and boto3 always hands it back
    as decimal.Decimal, which json.dumps refuses to serialise on its own.
    This is the classic Python trap in this tutorial: forget the
    conversion and every response with a number in it throws a
    TypeError. A Decimal with no fractional part becomes an int (so a
    quantity stays a whole number instead of turning into "5.0"); anything
    else becomes a float (so a price keeps its cents).
    """
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, list):
        return [decimalise(v) for v in value]
    if isinstance(value, dict):
        return {key: decimalise(v) for key, v in value.items()}
    return value


def lambda_handler(event, context):
    # A Scan returns at most 1 MB per call, so keep going until DynamoDB
    # says there is no more. Sixty products fit in one page; a real table
    # would not.
    items = []
    start_key = None
    while True:
        kwargs = {'ExclusiveStartKey': start_key} if start_key else {}
        page = table.scan(**kwargs)
        items.extend(page.get('Items', []))
        start_key = page.get('LastEvaluatedKey')
        if not start_key:
            break

    # CORS headers are added by the Function URL's own CORS setting (step
    # 3), so the response only needs the content type.
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({'items': decimalise(items), 'count': len(items)}),
    }
