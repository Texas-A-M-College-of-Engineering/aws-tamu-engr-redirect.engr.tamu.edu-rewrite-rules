"""
Rewrite rules testing application

Author: Blake Dworaczyk <blaked@tamu.edu>
"""

import argparse
import copy
from typing import Dict, List, Tuple
import json
import os
from pprint import pprint
import random
import string
from junit_xml import TestSuite, TestCase
import subprocess
import sys


class RewriteTester:
    def __init__(self, test_dir: str, debug: bool):
        self._test_dir = test_dir
        self._debug = debug
        with open(os.path.abspath(f'{test_dir}/event-template.json')) as fp:
          self._event_template = json.load(fp)

    @staticmethod
    def random_string(chars = string.ascii_lowercase + string.digits, n=10):
	    return ''.join(random.choice(chars) for _ in range(n))

    def _get_tests(self) -> Dict:
      with open(os.path.abspath(f'{self._test_dir}/tests.json')) as fp:
        return json.load(fp)

    def _write_tests(self, tests: Dict):
      with open(os.path.abspath(f'{self._test_dir}/tests.json'), 'w') as fp:
        json.dump(tests, fp, indent=2, sort_keys=True)

    @staticmethod
    def parse_event_uri(event_url: str) -> Tuple[str, str]:
      event_url_split = event_url.split('/')
      return event_url_split[0], '/' + '/'.join(event_url_split[1:]) if len(event_url_split) > 1 else '/'

    def _generate_and_write_cf_event(self, url: str) -> Dict:
      hostname, uri = self.parse_event_uri(event_url=url)
      # Parse out the querystring
      uri_and_qs = uri.split('?')
      uri = uri_and_qs[0]
      querystring = uri_and_qs[1] if len(uri_and_qs) > 1 else ''

      # Base the event input on the template
      event = copy.deepcopy(self._event_template) # type: Dict
      event['Records'][0]['cf']['request']['headers']['host'][0]['value'] = hostname
      event['Records'][0]['cf']['request']['uri'] = uri
      event['Records'][0]['cf']['request']['querystring'] = querystring

      event_filename = self.random_string() + '.json'
      with open(f'/tmp/{event_filename}', 'w') as fp:
        json.dump(event, fp)

      return event_filename

    def _get_rewrite_rules(self) -> Dict:
      with open(os.path.abspath(f'{self._test_dir}/../rules/rules.json'), encoding='UTF-8') as fp:
        return json.load(fp)

    def _find_missing_tests(self) -> List[str]:
      tests = self._get_tests()
      rewrite_rules = self._get_rewrite_rules()
      missing_tests = []
      for rewrite_rule in rewrite_rules:
        # If we don't have a hostname, then skip this one
        if 'H=' not in rewrite_rule:
          continue

        rule_match = rewrite_rule.split(' ')[0]
        hostname = rewrite_rule.split('H=')[1].split('|')[0].split(',')[0].split('^')[-1].split('$')[0]
        rule_name = hostname + rule_match
        if rule_name not in tests:
          missing_tests.append(rule_name) 

      return missing_tests

    def build_missing_tests(self):
      # read the current tests
      tests = self._get_tests()

      # read the rules file
      rewrite_rules = self._get_rewrite_rules()

      # Go through the rules and determine if we need to run any
      for rewrite_rule in rewrite_rules:
        # If we don't have a hostname, then skip this one
        if 'H=' not in rewrite_rule:
          continue
        rule_match = rewrite_rule.split(' ')[0]
        rewrite_target = rewrite_rule.split(' ')[1]
        hostname = rewrite_rule.split('H=')[1].split('|')[0].split(',')[0].split('^')[-1].split('$')[0]
        rule_name = hostname + rule_match
        #result_status = "301"
        #if len(rewrite_rule.split('R=')) > 1:
        #  result_status = rewrite_rule.split('R=')[1].split(',')[0].split(']')[0]
        if self._debug:
          print(f'checking for test {rule_name}')
        # We already have a test for this rule, skip it
        if rule_name in tests:
          continue
        print(f'Failed to find test for {rule_name}')

        # We don't have a test for this rewrite rule, generate one
        if rule_match.endswith('(.*)'):
          uri = '/' + '/'.join(rule_match.split('^')[-1].split('/')[0:-1]) + '/some/file.html'
        else:
          uri = rule_match.split('^')[-1].split('$')[0]
        #if '/$1' in rewrite_target:
        #  result_location = rewrite_target.replace('/$1', '/some/file.html')
        #else:
        #  result_location = rewrite_target

        event_url = (hostname + uri).replace('//', '/')
        test_output = self._get_test_output(test_name=rule_name, event_url=event_url)
        test = {
          'event_url': event_url,
          'result_status': test_output['status'],
          'result_location': test_output["headers"]["location"][0]["value"]
        }

        if self._debug:
          print(f'Created test "{rule_name}":')
          pprint(test)

        # To ensure that we can continue in case of an error, update the test file after each result
        tests[rule_name] = test
        self._write_tests(tests)


    # Run all tests in the tests.json file
    def run_all_tests(self):
      # Error out if we haven't created a test for each rule
      missing_tests = self._find_missing_tests()
      if missing_tests:
        print('The following tests have not been created:')
        pprint(missing_tests)
        print('Failing because of the above missing tests!')
        sys.exit(2)

      tests = self._get_tests()
      # Use this for better test output in the pipeline
      junit_test_cases = []

      if self._debug:
        print('Found the following tests to run:')  
        for test in tests:
          print(test)
        print()

      success = True
      results = {}
      passed = 0
      for test_name, test in tests.items():
        res, test_case = self.run_test(test_name, test)
        junit_test_cases.append(test_case)
        if res:
          passed += 1
        results[test_name] = res
        success = success and res

      print(f'Tests passed: {passed}/{len(results.keys())} tests')
      if passed < len(results.keys()):
        print('The following tests failed:')
        pprint([test_name for test_name, test_result in results.items() if not test_result])

      with open(os.path.abspath(f'{self._test_dir}/temp_results/tests.xml'), 'w') as fp:
        TestSuite.to_file(fp, [TestSuite(name='Rewrite rules tests', test_cases=junit_test_cases)])

      if not success:
        sys.exit(1)

    def _get_test_output(self, test_name: str, event_url: str) -> Dict:
      # Write a test event and test output file for the tester
      event_filename = self._generate_and_write_cf_event(url=event_url)

      process = subprocess.Popen(f'./test_event.sh /tmp/{event_filename} ../rules/rules.json'.split(' '), 
          stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd='sam')
      stdout, stderr = process.communicate()
      os.unlink(f'/tmp/{event_filename}')
      if self._debug:
        print(stdout.decode('utf-8'))
      if process.returncode != 0:
        print(stderr.decode('utf-8'))
        print('sam invoke completely failed!')
        return {}

      return json.loads(stdout)

    # Run a test and compare the output to the expected output
    def run_test(self, test_name: str, test: Dict[str, str]) -> Tuple[bool, TestCase]:
      print(f'Running test: "{test_name}"')

      if self._debug:
        print('Test details:')
        pprint(test)

      result_dict = self._get_test_output(test_name=test_name, event_url=test['event_url'])
      
      res = self._result_dict_matches_desired(test_dict=test, result_dict=result_dict)
      if res:
        print(f'Test "{test_name}" PASSED')
      else:
        print(f'Test "{test_name}" FAILED')

      # Keep the output in junit format
      test_case = TestCase(name=test_name, classname=test['event_url']) 
      if not res:
        test_case.add_failure_info(message='Redirect test failed', output=str(result_dict))

      return res, test_case

    def _result_dict_matches_desired(self, test_dict: dict, result_dict: dict):
      res = True
      if int(test_dict['result_status']) != int(result_dict['status']):
        print(f'Status {result_dict["status"]} doesn\'t match {test_dict["result_status"]}')
        res = False
      if test_dict['result_location'] != result_dict['headers']['location'][0]['value']:
        print(f'Location {result_dict["headers"]["location"][0]["value"]} does not match ' 
          f'{test_dict["result_location"]}')
        res = False
      return res

    def sam_build(self):
      process = subprocess.Popen(f'sam build --use-container'.split(' '), 
          stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd='sam')
      stdout, stderr = process.communicate()
      print(stdout.decode('utf-8'))
      print(stderr.decode('utf-8'))
      if process.returncode != 0:
        print('sam build failed... aborting')
        sys.exit(2)



def main():
    parser = argparse.ArgumentParser(
        add_help='Runs tests to ensure that the redirect rules provide the expected output')
    parser.add_argument('--test_path', help='The directory that contains the tests', required=True)
    parser.add_argument('--build_sam', help='Build the SAM function before tests', action='store_true')
    parser.add_argument('--debug', help='Enable debugging output', action='store_true')
    parser.add_argument('--build_missing_tests', 
                        help='Modify the tests.json file to generate any tests that are missing, and use the ' 
                             'results of running the rewrite rules. This provides a good way to generate tests, but ' 
                             'generated test results should be checked for accuracy.', action='store_true')
    args = parser.parse_args()

    rewrite_tester = RewriteTester(test_dir=args.test_path, debug=args.debug)

    if args.build_sam:
      rewrite_tester.sam_build()

    if args.build_missing_tests:
      rewrite_tester.build_missing_tests()
    else:
      rewrite_tester.run_all_tests()


if __name__ == "__main__":
    main()
