import os
import yaml
import unittest
import requests
import pandas as pd
from ea_parsing.appeal_document import Appeal


class TestResults(unittest.TestCase):

    def test_lessons_learned_extraction(self):
        """
        Compare appeal document parse results against previously saved expected results.
        """
        # Read in the lessons learned results from yaml files
        lessons_learned_results = {}
        TESTS_DIR = os.path.dirname(os.path.realpath(__file__))
        files = os.listdir(os.path.join(TESTS_DIR, 'results'))
        for i, file in enumerate(files):

            # Get MDR code and validated results
            mdr_code = os.path.splitext(file)[0]
            validated_lessons_learned = yaml.safe_load(open(os.path.join(TESTS_DIR, 'results', file)))

            with self.subTest(msg=mdr_code, i=i):

                # Get appeal final report
                appeal = Appeal(mdr_code=mdr_code)
                final_report = appeal.final_report

                # Get the document lines
                document_lines_path = os.path.join(TESTS_DIR, 'raw_lines', f'{mdr_code}.csv')
                if os.path.isfile(document_lines_path):
                    final_report.raw_lines_input = pd.read_csv(document_lines_path, index_col=0)

                # Get lessons learned
                lessons_leared_results = final_report.lessons_learned

                # Compare number of lessons learned
                self.assertEqual(
                    len(lessons_leared_results),
                    len(validated_lessons_learned),
                    f"Different number of lessons learned for MDR code: {mdr_code}"
                )

                # Loop through lessons to compare
                for i, lesson_result in enumerate(lessons_leared_results):
                    lesson_validated = validated_lessons_learned[i]

                    # Compare title and sector title
                    self.assertEqual(
                        lesson_result['title']['text'],
                        lesson_validated['title']['text'],
                        f"Different titles for MDR code: {mdr_code}\n\nResults: {lesson_result['title']}\nValidated results: {lesson_validated['title']}"
                    )
                    self.assertEqual(
                        lesson_result['sector_title'],
                        lesson_validated['sector_title'],
                        f"Different sector titles for MDR code: {mdr_code}\n\nResults: {lesson_result['sector_title']}\nValidated results: {lesson_validated['sector_title']}"
                    )

                    # Compare content length
                    validated_content = pd.DataFrame(
                        [item['text'] for item in lesson_validated['content']], 
                        columns=['content']
                    )
                    results_content = pd.DataFrame(
                        [item['text'] for item in lesson_result['content']], 
                        columns=['content']
                    )
                    self.assertEqual(
                        len(lesson_validated['content']),
                        len(lesson_result['content']),
                        f"Different length of content for MDR code: {mdr_code}, sector: {lesson_result['sector_title']}\n\nResults: {results_content}\nValidated results: {validated_content}"
                    )

                    # Compare content
                    self.assertTrue(
                        validated_content.equals(results_content),
                        f"Lessons learned contents does not match for MDR code: {mdr_code}, sector: {lesson_result['sector_title']}\n\n{results_content.compare(validated_content)}"
                    )