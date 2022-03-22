# aws-tamu-engr-redirect.engr.tamu.edu-rewrite-rules
Rewrite rules, tests, and pipeline for redirect.engr.tamu.edu

## Usage Summary
Begin by cloning this repository, and ensure that you clone it recursively to 
include the submodule:

```bash
$ git clone --recurse-submodules https://github.com/Texas-A-M-College-of-Engineering/aws-tamu-engr-redirect.engr.tamu.edu-rewrite-rules
```

Create a new feature or bugfix branch: 

```bash
$ git checkout -b 'feature-add-site-mysite.engr.tamu.edu'
```

Modify the `rules/rules.json` file in the rules directory. Tests should be created 
for each rule. Rules cannot be deployed if they do not have an associated test.
You can find more details about creating tests in the below section on
testing. When you are finished, push your new rules and tests to github.com:

```bash
$ git add rules/rules.json
$ git add tests/tests.json
$ git commit -m "Add rewrite rule for mysite.engr.tamu.edu"
$ git push --set-upstream origin feature-add-site-mysite.engr.tamu.edu
```

Go to the GitHub repo in your web browser and create a PR for your new branch 
against the main branch:

```
https://github.com/Texas-A-M-College-of-Engineering/aws-tamu-engr-redirect.engr.tamu.edu-rewrite-rules/pull/new/feature-add-site-mysite.engr.tamu.edu
```

This will cause the automated tests to run. If all tests pass, you can merge your 
PR and the rules will be live. Keep in mind that caching happens at both the CloudFront
edge locations and the Lambda@Edge function, so you may not see the changes
reflected immediately

## Rules
Simply make modifications to the *rules.json* files in the rules directory in a 
branch created for that particular change. The best method for making changes is
to look at an existing example from somewhere in the ruleset and modifying that.
Ensure that you keep the rules in alphabetical order based on the hostname to
make it easier to browse and view the rules.

## Tests
Tests should be written for every single rule that you add. This helps ensure
that rules do not inadvertently match some other rule in an unexpected way, and
hence cause hard to find rewrite issues. 

This is also important since caching means that the rule will not take effect
immediately, and so creating a test will ensure that the rule should work as 
expected when it does take effect.

There are two methods that you can use to create test rules. **You will need to
have Docker installed to run or generate tests locally.**

### Setting up the local testing environment
You should install Docker and Python 3.8+, then set up your testing environment. 
Do this from the root of your repo:

```bash
$ python3 -m venv venv
$ source venv/bin/activate
$ pip install -r ./requirements.txt
```

Additionally, you should ensure that you have the `jq` CLI utility installed.
On a Mac, you can install it with Homebrew:

```bash
$ brew install jq
```

### Manually create the rule
You can edit the *tests/tests.json* file and add a testing rule yourself. You
should ensure that the rules remain in alphabetical order to make browsing the
tests easier. The easier way to do this is to automatically generate the rule,
which is explained in the next section.

### Automatically create the rule and edit it
You can run the *rewrite_tester.py* utility in the *tester* directory to generate 
tests as follows: 

```bash
$ source venv/bin/activate
$ python tester/rewrite_tester.py --test_path tests --debug --build_missing_tests
```

**Note: The first time that you checkout and run this project you'll need to
build the Lambda. You can do that by adding the --build_sam flag as follows:**

```bash
$ python tester/rewrite_tester.py --test_path tests --debug --build_missing_tests --build_sam
```


This will automatically add any testing rules to the tests file. You should
examine the *tests/tests.json* file and ensure that the new rules are correct

### Test file format
An excerpt from the tests file with two tests looks like this:

```json
{
  "bigdata.tamu.edu^/(.*)": {
    "event_url": "bigdata.tamu.edu/some/file.html",
    "result_location": "https://tamids.tamu.edu",
    "result_status": "301"
  },
  "biomed.tamu.edu^/dmaitland/?(.*)": {
    "event_url": "biomed.tamu.edu/dmaitland/some/file.html",
    "result_location": "https://biomed-dmaitland.engr.tamu.edu",
    "result_status": "301"
  }
}
```
The name of the test is the hostname and the rewrite match concatenated together.
It contains the following properties:
| Property | Description |
| -------- | ----------- |
| event_url | The URL that will be used as the rewrite source |
| result_location | The expected result of the rewrite |
| result_status | The expected HTTP status of the rewrite |

### Testing locally

During development, it might be desirable to test rewrites locally before 
deploying This can be accomplished by creating a json file based on the 
*tests/event-template.json* file and then running the *test_event.sh* script 
in the *sam* directory. A typical invocation might look like this:

```bash
$ ./test_event.sh /tmp/my_event.json ../rules/rules.json
```

The important output is the last line, and might look something like this:

```json
{"status":"301","statusDescription":"Found","headers":{"location":[{"key":"Location","value":"https://tamids.tamu.edu"}]}}
```

You can also run the entire test suite locally from the project root:

```bash
$ python tester/rewrite_tester.py --test_path tests --debug
```

## Deployment Workflow

Deploying changes to the rewrite rules should follow this workflow:
1. If this is a new site, i.e. no rewrite rules exist for this site. You need to
   add the site to the list at [aws-tamu-engr-redirect.engr.tamu.edu](https://github.com/Texas-A-M-College-of-Engineering/aws-tamu-engr-redirect.engr.tamu.edu.git)
2. Commit and push a new version with tests and an updated rules.json file to a 
   custom branch, i.e. feature-add-bigdata-rewrites
3. Submit a PR to merge the changes to the *main* branch
4. The merge is only possible if the tests pass
5. Be aware that changes to the rules will take time to be reflected. On 
   average: ((1/2 * CF cache TTL) + (1/2 * Lambda rule cache TTL)) / 2
