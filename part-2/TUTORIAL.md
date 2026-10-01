# Build a CRUD app with Lattice Grid, Python and DynamoDB. Part 2: add and delete

Part 1 ended with a page that reads products from your own DynamoDB table
through a Lambda function. This part adds the two verbs that make it an
application: adding a product through the grid's built-in form, and deleting
one from the right-click menu. Both land in DynamoDB before the page moves on.

Everything from part 1 carries over. You will change the function's code,
widen its permissions and its URL settings, and swap the page.

**Source:** the `part-2` folder of
[toclocoinc/lattice-tutorial-crud-dynamodb-python](https://github.com/toclocoinc/lattice-tutorial-crud-dynamodb-python)
(Code, Download ZIP). This part needs Lattice Grid 1.83.0 or later, which is
the version the page loads.

## Step 1: teach the function two more verbs

Open **Lambda**, then `products-read`, then the **Code** tab. Replace the
contents of `lambda_function.py` with `lambda/lambda_function.py` from the
download and choose **Deploy**.

The function now looks at the request's method:

- `GET` returns every product, as before.
- `POST` takes a product as JSON, gives it a `sku` if the page did not, stamps
  `updated` with today's date, and writes it with a condition that refuses to
  overwrite an existing `sku`. It answers with the product as stored.
- `DELETE` takes `?sku=` and removes that product.

The condition on the write is the one line worth pausing on, and it reads
almost the same in Python as it does in the Node edition:

```python
try:
    table.put_item(Item=item, ConditionExpression='attribute_not_exists(sku)')
except ClientError as err:
    if err.response['Error']['Code'] == 'ConditionalCheckFailedException':
        return response(409, {'error': 'That sku already exists'})
    raise
```

Without the condition, two people adding a product with the same `sku` would
silently overwrite each other. With it, the second one gets a clear "already
exists" answer that the page can show. boto3 reports the failure as a
`ClientError` with an error code rather than a named exception class; the
`except` clause above is how a Python Lambda has to spot it.

The sku the function assigns when the page leaves one blank is a base 36
timestamp, the same shape the Node edition generates, built by hand because
Python has no built-in number-to-base-36 conversion:

```python
def new_sku():
    digits = '0123456789abcdefghijklmnopqrstuvwxyz'
    n = int(time.time() * 1000)
    out = []
    while n:
        n, r = divmod(n, 36)
        out.append(digits[r])
    return 'SKU-' + ''.join(reversed(out)).upper()
```

## Step 2: allow the new verbs through the URL

The Function URL's CORS setting from part 1 allows every origin but only the
`GET` method, so the browser would refuse to send a `POST` or a `DELETE`.

1. On the function's **Configuration** tab, choose **Function URL**, then
   **Edit**.
2. Under **Configure cross-origin resource sharing (CORS)**, set **Allow
   methods** to `GET`, `POST` and `DELETE`, and **Allow headers** to
   `content-type`. The page sends that header with the JSON body of a POST.
3. Save.

## Step 3: give the function the permission it needs, and no more

Part 1 attached `AmazonDynamoDBReadOnlyAccess`, which is enough to read and
nothing else. The function now writes, so it needs `PutItem` and `DeleteItem`,
and the tidy way to grant them is a policy that names this one table.

1. On the **Configuration** tab, choose **Permissions**, then click the role
   name under **Execution role**. IAM opens.
2. Under **Permissions policies**, tick `AmazonDynamoDBReadOnlyAccess` and
   choose **Remove**. Confirm.
3. Choose **Add permissions**, then **Create inline policy**. Switch the editor
   to **JSON** and paste `iam/products-policy.json` from the download. Replace
   `REGION` with your region (`eu-west-2` for London) and `ACCOUNT_ID` with the
   twelve-digit account id shown at the top right of the console.
4. Choose **Next**, name it `products-table`, and **Create policy**.

The policy allows scan, get, put, update and delete on the `Products` table
and nothing on any other table. Update is not used yet; part 3 needs it, and it
saves a return trip to IAM.

## Step 4: the page

Open `web/index.html` from the download and paste your Function URL into the
same line as in part 1. Open the file in a browser. The page itself did not
change from part 1's edition; a web page calling a Function URL has no idea
what language answers it.

Three things are new.

**Add product** opens the grid's built-in form for a new row. Fill in a name,
category, quantity and price, and choose Save. The form validates the fields
the way the grid's own editors do, then calls the `create` hook you gave it:

```js
rowForm: {
  fields: [
    { field: 'name', label: 'Product' },
    { field: 'category', label: 'Category' },
    { field: 'quantity', label: 'In stock' },
    { field: 'price', label: 'Price' },
  ],
  create: (values) => api('POST', '', values),
},
```

`create` posts the values to the function and returns what comes back: the
product as DynamoDB stored it, with the `sku` the server assigned. The grid
adds that row, scrolls to it and selects it. If the function refuses, the form
stays open with your values and a retry, and the status line shows the
server's reason.

**Right-click a row** and the menu has the grid's own items, then a Delete for
that product:

```js
contextMenu: (p, defaults) => [
  ...defaults,
  { separator: true },
  {
    name: 'Delete ' + p.data.name,
    action: async () => {
      if (!confirm('Delete ' + p.data.name + '?')) return;
      await api('DELETE', '?sku=' + encodeURIComponent(p.key));
      grid.rows.apply({ remove: [p.key] });
    },
  },
],
```

`p` describes the cell that was clicked: `p.key` is the row's key, the `sku`,
and `p.data` is your product object. The action deletes on the server first
and only then removes the row from the grid, so a failed delete leaves the
row where it was.

**The `api` helper** is eight lines that wrap `fetch`, set the JSON header
when there is a body, and turn a non-2xx answer into an error carrying the
function's message. Every call in the page goes through it, and every number
it receives has already passed through the function's `decimalise()`, so the
page never sees a `Decimal` or anything like one.

## Step 5: check the table

Add a product, then open **DynamoDB**, **Tables**, `Products`, **Explore table
items**. The new product is there with the `sku` the function chose. Delete it
from the page and refresh the console; it is gone.

## What you have

A page that reads, adds and deletes against your own table, with every write
happening on the server before the page reflects it. The grid supplied the
form and the menu; you supplied two verbs and a policy, this time in Python.

## Next

**Part 3: edit in place.** Cells become editable and each committed change is
patched to DynamoDB while the grid shows it, with the old value put back if
the server says no. The page also goes full screen on a button, and the form
moves from a drawer into a panel of your own.

## Cleaning up

As in part 1: delete the function, the table and the role. The inline policy
goes with the role.
