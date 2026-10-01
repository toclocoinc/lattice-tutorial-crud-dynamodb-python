# Build a CRUD app with Lattice Grid, Python and DynamoDB. Part 3: edit in place

Part 2 gave the page add and delete. This part makes the cells themselves
editable, with each change patched to DynamoDB the moment it is committed and
put back if the server refuses it. It also adds a full-screen button and moves
the row form out of its drawer into a panel that is part of the page.

**Source:** the `part-3` folder of
[toclocoinc/lattice-tutorial-crud-dynamodb-python](https://github.com/toclocoinc/lattice-tutorial-crud-dynamodb-python).
Needs Lattice Grid 1.83.0 or later.

## Step 1: the function learns PATCH

On the function's **Code** tab, replace `lambda_function.py` with
`lambda/lambda_function.py` from the download and choose **Deploy**.

`PATCH` takes `?sku=` and a JSON body holding only the fields that changed. It
builds the update one `SET` clause at a time from an allow-list of fields,
stamps `updated`, and refuses to update a product that does not exist, so a
PATCH can never create one by accident. It answers with the whole product as
stored:

```python
EDITABLE = ('name', 'category', 'quantity', 'price')

names, values, sets = {}, {}, []
for field in EDITABLE:
    if field not in changes:
        continue
    v = to_decimal(changes[field]) if field in ('quantity', 'price') else str(changes[field])
    names['#' + field] = field
    values[':' + field] = v
    sets.append(f'#{field} = :{field}')
```

The allow-list matters. A PATCH endpoint is a public door in this tutorial,
and without the list a caller could set any attribute on any product. With
it, the function only ever changes the four fields the page edits. `quantity`
and `price` go through `to_decimal()`, the same conversion part 2 uses on
create, because DynamoDB only accepts `Decimal` for a number, never the
`float` that `json.loads` hands back.

The condition that stops a PATCH from creating a row is the mirror image of
part 2's create condition:

```python
ConditionExpression='attribute_exists(sku)',  # never create by accident
```

If it fails, boto3 raises the same `ConditionalCheckFailedException`
`ClientError` part 2 catches on create; here it means "no such product"
rather than "already exists", so the function answers 404 instead of 409.

## Step 2: allow PATCH through the URL

**Configuration**, **Function URL**, **Edit**. Under the CORS settings add
`PATCH` to **Allow methods**, keeping `GET`, `POST` and `DELETE` and the
`content-type` header. Save. The IAM policy from part 2 already includes
`UpdateItem`, so nothing changes there.

## Step 3: the page

Paste your Function URL into `web/index.html` as before and open it. The page
is unchanged from the Node edition; nothing about the front end depends on
which language the Function URL runs.

**Editable cells.** Four columns now carry `edit: true`. Double-click a
quantity, type a new number, press Enter. The cell shows the new value at
once, and the grid calls the `commit` hook you gave it:

```js
edit: {
  commit: (write) => api('PATCH', '?sku=' + encodeURIComponent(write.key), { [write.colId]: write.value }),
},
```

`write` names the row's key, the column and the new value, and the promise
you return settles the write: resolve and the cell stays, reject and the grid
puts the old value back and fires `cell:reverted`, which the status line
reports. That is optimistic write-back: the user never waits for the network,
and a refusal is visible rather than silent.

Try it against the rules: clear a name and press Enter. The function answers
400, the cell reverts, and the status line says why.

**Full screen.** The button calls `grid.maximise.toggle()`. The grid fills
the window, remembering where it came from and its scroll position, and the
same button or Escape puts it back.

**The form in a panel.** The row form has two new lines:

```js
rowForm: {
  container: '#form',
  trigger: false,
  ...
},
```

With a container, the form renders inside that element instead of over the
grid as a drawer. `trigger: false` takes double-click away from the form,
because the cells now want it; the menu gains an **Edit in form** item that
calls `grid.form.open(p.key)` instead. Right-click a row, choose it, and the
row appears in the side panel with the same fields as part 2's form. Save goes
through the same `commit` hook as a cell edit, one call per changed field, so
nothing about persistence changed when the form moved. **Add product** opens
the same panel over an empty record, and `create` handles it as in part 2.

## Step 4: check the table

Change a price, then look at the item in **Explore table items**. The price
and the `updated` date have moved. Change it again in the console instead and
reload the page; the grid shows the console's value, because the page has no
copy of the truth beyond what the function returns.

## What you have

A grid that reads, adds, edits and deletes against your own table, with every
change confirmed by the server and every refusal shown. The page is under a
hundred lines of script, and the parts that would take a week to build by hand
(the form, the menu, the optimistic edit with revert, the full-screen mode)
came from the grid. Everything server-side, including the Decimal conversion
that the Node edition never had to think about, is under two hundred lines of
Python across three files.

## Where to go next

Two things this series left out on purpose. The Function URL has no
authentication, so anyone with the URL can change your products; the next
step for a real application is an authorizer in front of it, and the grid does
not care which, Python or otherwise. And the function returns every product on
every load, which is right at sixty rows and wrong at sixty thousand; the
grid's pushdown sources move filtering, sorting and paging into the function
so the browser only asks for what it shows. Both are covered in the guides.

## Cleaning up

As in part 1: delete the function, the table and the role.
