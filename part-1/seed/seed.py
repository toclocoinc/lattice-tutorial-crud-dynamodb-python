"""Part 1: upload the demo products into the DynamoDB table.

    cd seed
    pip install -r requirements.txt
    AWS_REGION=eu-west-2 python3 seed.py

Uses whatever AWS credentials your shell already has (the same ones the AWS
CLI uses: environment variables, a profile, or SSO). Set AWS_REGION to the
region you created the table in, and TABLE_NAME if you did not call it
"Products".
"""
import json
import os
from decimal import Decimal
from pathlib import Path

import boto3

TABLE = os.environ.get('TABLE_NAME', 'Products')

# json.load hands back float for every number; DynamoDB only accepts
# Decimal, so convert with parse_float the way the table itself expects.
products_path = Path(__file__).with_name('products.json')
products = json.loads(products_path.read_text(encoding='utf-8'), parse_float=Decimal)

table = boto3.resource('dynamodb').Table(TABLE)

# batch_writer() buffers up to 25 items per request (DynamoDB's own limit)
# and retries anything DynamoDB hands back as unprocessed, so there is no
# manual chunking or retry loop to write.
with table.batch_writer() as batch:
    for i, product in enumerate(products, start=1):
        batch.put_item(Item=product)
        if i % 25 == 0 or i == len(products):
            print(f'wrote {i} of {len(products)}')

print(f'done: {len(products)} products in table "{TABLE}"')
