import os
import yaml
import unittest
from functools import cached_property
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
            validated_results_files=self.get_file_paths('lessons_learned_results'),
            type_='lessons_learned'
        )

    def test_challenges_extraction(self):
        """
        """
        self.compare_validated_results(
            validated_results_files=self.get_file_paths('challenges_results'),
            type_='challenges'
        )

    def get_file_paths(self, folder_name):
        """
        Get a list of paths to the files in folder_name,
        where folder_name is the name of a folder in the tests directory.
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

                # Read in the document lines: raw and processed
                raw_lines_path = os.path.join(self.TESTS_DIR, 'raw_lines', f'{mdr_code}.csv')
                if os.path.isfile(raw_lines_path):
                    final_report.raw_lines_input = pd.read_csv(raw_lines_path, index_col=0)
                else:
                    if final_report.raw_lines is not None:
                        final_report.raw_lines.to_csv(raw_lines_path)

                processed_lines_path = os.path.join(self.TESTS_DIR, 'processed_lines', f'{mdr_code}.csv')
                if os.path.isfile(processed_lines_path):
                    final_report.lines_input = pd.read_csv(processed_lines_path, index_col=0)
                else:
                    if final_report.lines is not None:
                        final_report.lines.to_csv(processed_lines_path)

                # Get results
                if type_ == 'lessons_learned':
                    results = final_report.lessons_learned
                elif type_ == 'challenges':
                    results = final_report.challenges

                # Compare number of results
                self.assertEqual(
                    len(results),
                    len(validated_results),
                    f"Different number of sections for MDR code: {mdr_code}"
                )

                # Compare section titles
                results_titles = [x['title']['text'] for x in results]
                validated_titles = [x['title']['text'] for x in validated_results]
                self.assertListEqual(
                    results_titles,
                    validated_titles,
                    f"""
                    Different titles for MDR code: {mdr_code}

                    Results: {results_titles}
                    Validated results: {validated_titles}
                    """
                )

                # Compare section sectors
                results_sectors = [x['sector_title'] for x in results]
                validated_sectors = [x['sector_title'] for x in validated_results]
                self.assertListEqual(
                    results_sectors,
                    validated_sectors,
                    f"""
                    Different sector titles for MDR code: {mdr_code}

                    Results: {results_sectors}
                    Validated results: {validated_sectors}
                    """
                )

                # Loop through section results to compare excerpts
                for i, result in enumerate(results):
                    validated_result = validated_results[i]

                    # Compare section items - "excerpts"
                    self.assertListEqual(
                        result['items'],
                        validated_result['items'],
                        f"""
                        Section items do not match for MDR code: {mdr_code}, sector: {result['sector_title']}

                        Results: {result['items']}
                        Validated results: {validated_result['items']}
                        """
                    )
