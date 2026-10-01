# Part 3: edit in place, full screen, and the form inside the page (Python edition)

Source for part 3 of the Python edition. Builds on part 2. The guide is on
the Lattice Grid site and in [`TUTORIAL.md`](TUTORIAL.md).

| File | What it is |
| --- | --- |
| `lambda/lambda_function.py` | The function with GET, POST, PATCH and DELETE. Paste it over part 2's code and deploy. |
| `lambda/test_lambda_function.py` | Unit tests against a stubbed DynamoDB client. `cd lambda && pip install boto3 && python3 -m unittest discover` |
| `web/index.html` | The page: editable cells that PATCH as you commit them, a Full screen button, and the row form drawn in a side panel instead of over the grid. |

The IAM policy from part 2 already allows `UpdateItem`, so nothing changes
in IAM. The Function URL's CORS needs PATCH added to its allowed methods.
