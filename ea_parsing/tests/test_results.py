import os
import yaml
import unittest
from functools import cached_property
import requests
import pandas as pd
from ea_parsing.appeal_document import Appeal


class TestResults(unittest.TestCase):

    @cached_property
    def TESTS_DIR(self):
        return os.path.dirname(os.path.realpath(__file__))


    def test_lessons_learned_extraction(self):
        """
        Compare appeal document parse results against previously saved expected results.
        """
        self.compare_validated_results(
            validated_results_files = self.get_file_paths('lessons_learned_results'),
            type_='lessons_learned'
        )


    def test_challenges_extraction(self):
        """
        """
        self.compare_validated_results(
            validated_results_files = self.get_file_paths('challenges_results'),
            type_='challenges'
        )


    def get_file_paths(self, folder_name):
        """
        Get a list of paths to the files in folder_name, where folder_name is the name of a folder in the tests directory.
        """
        paths = []
        for root, dirs, filenames in os.walk(os.path.join(self.TESTS_DIR, folder_name)):
            for file in filenames:
                paths.append(os.path.abspath(os.path.join(root, file)))
            
        return paths


    def compare_validated_results(self, validated_results_files, type_):
        """
        """
        # Read in the results from yaml files
        for i, path in enumerate(validated_results_files):

            # Get MDR code and validated results
            mdr_code = os.path.splitext(os.path.basename(path))[0]
            validated_results = yaml.safe_load(open(path))

            with self.subTest(msg=mdr_code, i=i):

                # Get appeal final report
                appeal = Appeal(mdr_code=mdr_code)
                final_report = appeal.final_report

                # Read in the document lines
                document_lines_path = os.path.join(self.TESTS_DIR, 'raw_lines', f'{mdr_code}.csv')
                if os.path.isfile(document_lines_path):
                    final_report.raw_lines_input = pd.read_csv(document_lines_path, index_col=0)

                # Get results
                if type_=='lessons_learned':
                    results = final_report.lessons_learned
                elif type_=='challenges':
                    results = final_report.challenges

                # Compare number of results
                self.assertEqual(
                    len(results),
                    len(validated_results),
                    f"Different number of sections for MDR code: {mdr_code}"
                )

                # Loop through section results to compare
                for i, result in enumerate(results):
                    validated_result = validated_results[i]

                    # Compare title and sector title
                    self.assertEqual(
                        result['title']['text'],
                        validated_result['title']['text'],
                        f"Different titles for MDR code: {mdr_code}\n\nResults: {result['title']}\nValidated results: {validated_result['title']}"
                    )
                    self.assertEqual(
                        result['sector_title'],
                        validated_result['sector_title'],
                        f"Different sector titles for MDR code: {mdr_code}\n\nResults: {result['sector_title']}\nValidated results: {validated_result['sector_title']}"
                    )

                    # Compare content length
                    validated_content = pd.DataFrame(
                        [item['text'] for item in validated_result['content']], 
                        columns=['content']
                    )
                    results_content = pd.DataFrame(
                        [item['text'] for item in result['content']], 
                        columns=['content']
                    )
                    self.assertEqual(
                        len(validated_result['content']),
                        len(result['content']),
                        f"Different length of content for MDR code: {mdr_code}, sector: {result['sector_title']}\n\nResults: {results_content}\nValidated results: {validated_content}"
                    )

                    # Compare content
                    self.assertTrue(
                        validated_content.equals(results_content),
                        f"Section contents does not match for MDR code: {mdr_code}, sector: {result['sector_title']}\n\n{results_content.compare(validated_content)}"
                    )