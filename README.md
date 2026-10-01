# Lattice Grid tutorial: a CRUD application on Python and DynamoDB

Source for the Python edition of the step-by-step series at
https://www.latticegrid.dev/tutorials/. Each part is a folder with
everything that part asks you to paste or run. This is the same series as
[toclocoinc/lattice-tutorial-crud-dynamodb](https://github.com/toclocoinc/lattice-tutorial-crud-dynamodb)
(the Node edition), rewritten so the Lambda function and the seed script are
Python instead of JavaScript. The front end, the DynamoDB table, the Console
steps and every HTTP route are the same in both editions; only the language
behind the Function URL changes.

| Part | What you build | Folder |
| --- | --- | --- |
| 1 | A DynamoDB table with demo data, a Python Lambda that reads it, and a web page that shows it in a grid | [`part-1/`](part-1/) |
| 2 | Add a product through the grid's built-in form and delete one from the right-click menu, both landing in DynamoDB | [`part-2/`](part-2/) |
| 3 | Edit cells in place with optimistic write-back and revert, full screen, and the form rendered in a side panel | [`part-3/`](part-3/) |

Download everything with **Code, Download ZIP**, or clone the repository.
Each part's README lists what you need and what it costs to run.

**If you already built the Node edition:** the table, the data, the web
page and every route are identical. The only thing that changes is the code
you paste into the Lambda console, and the IAM role name it creates. You
can run this edition against a fresh table, or point part 1's `lambda_function.py`
at the table you already have.
