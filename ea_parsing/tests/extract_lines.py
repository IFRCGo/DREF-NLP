import os
import argparse
import pandas as pd
from ea_parsing.appeal_document import Appeal

parser = argparse.ArgumentParser()
parser.add_argument('-o', "--overwrite", action='store_true')
args = parser.parse_args()

# Read in the lessons learned results from yaml files
lessons_learned_results = {}
TESTS_DIR = os.path.dirname(os.path.realpath(__file__))
files = os.listdir(os.path.join(TESTS_DIR, 'results'))
for file in files:
    mdr_code = os.path.splitext(file)[0]

    # Get appeal final report
    appeal = Appeal(mdr_code=mdr_code)
    final_report = appeal.final_report
    
    # Extract the lines from the PDF documents and save
    document_lines_path = os.path.join(TESTS_DIR, 'results', f'{mdr_code}.csv')

    # Check whether to overwrite
    save_results = None
    if os.path.isfile(document_lines_path):
        if not args.overwrite:
            while True:
                save_results = input(f'\nOverwrite file {mdr_code}.csv? (y/n) ')
                if save_results in ['y', 'n']:
                    break

    # Save the results
    if save_results=='y' or args.overwrite or not os.path.isfile(document_lines_path):
        final_report.raw_lines.to_csv(document_lines_path, index=True)