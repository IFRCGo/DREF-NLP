import os
import yaml
import unittest
import requests
import pandas as pd


class TestResults(unittest.TestCase):

    def test_mdr_codes_results(self):
        """
        Compare appeal document parse results against previously saved expected results.
        """
        base_url = "http://127.0.0.1:8000"
        TESTS_DIR = os.path.dirname(os.path.realpath(__file__))

        # Read in the lessons learned results from yaml files
        lessons_learned_results = {}
        files = os.listdir(os.path.join(TESTS_DIR, 'results'))
        for file in files:
            mdr_code = os.path.splitext(file)[0]
            lessons_learned_results[mdr_code] = yaml.safe_load(open(os.path.join(TESTS_DIR, 'results', file)))

        # Loop through results
        for mdr_code, validated_results in lessons_learned_results.items():
            with self.subTest(msg=mdr_code):

                # Get MDR code parse results from API parse
                response = requests.post(
                    url=f'{base_url}/parse/', 
                    params={'mdr_code': mdr_code}
                )
                response.raise_for_status()
                results = response.json()

                # Compare results
                self.assertTrue(
                    results == validated_results, 
                    f'Results do not match expected results for MDR code {mdr_code}\n\nResults:\n{results}\n\nExpected results:\n{validated_results}'
                )