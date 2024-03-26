"""
Read in all validated results files for MDR codes, and save the raw and processed lines to speed up testing.
"""
import os
import argparse
from ea_parsing.appeal_document import Appeal

parser = argparse.ArgumentParser()
parser.add_argument('-o', "--overwrite", action='store_true')
parser.add_argument('-no', "--no_overwrite", action='store_true')
args = parser.parse_args()

# Get the paths to results files
lessons_learned_results = {}
TESTS_DIR = os.path.dirname(os.path.realpath(__file__))
challenge_results_files = os.listdir(os.path.join(TESTS_DIR, 'challenges_results'))
lessons_learned_results_files = os.listdir(os.path.join(TESTS_DIR, 'lessons_learned_results'))
files = list(set(challenge_results_files + lessons_learned_results_files))

# If no overwrite, don't bother getting files which are already saved
if args.no_overwrite:
    raw_lines_saved = os.listdir(os.path.join(TESTS_DIR, 'raw_lines'))
    files = [file for file in files if file not in raw_lines_saved]

# Loop through files and get final report lines
for file in files:
    mdr_code = os.path.splitext(file)[0]

    # Get appeal final report
    appeal = Appeal(mdr_code=mdr_code)
    final_report = appeal.final_report

    # Raw lines: check whether to overwrite, and save
    save_results = None
    raw_lines_path = os.path.join(TESTS_DIR, 'raw_lines', f'{mdr_code}.csv')
    if os.path.isfile(raw_lines_path):
        if (not args.overwrite) and (not args.no_overwrite):
            while True:
                save_results = input(f'\nOverwrite file {mdr_code}.csv? (y/n) ')
                if save_results in ['y', 'n']:
                    break
    if (save_results == 'y') or args.overwrite or not os.path.isfile(raw_lines_path):
        final_report.raw_lines.to_csv(raw_lines_path, index=True)

    # Processed lines: check whether to overwrite, and save
    save_results = None
    raw_lines_path = os.path.join(TESTS_DIR, 'processed_lines', f'{mdr_code}.csv')
    if os.path.isfile(raw_lines_path):
        if (not args.overwrite) and (not args.no_overwrite):
            while True:
                save_results = input(f'\nOverwrite file {mdr_code}.csv? (y/n) ')
                if save_results in ['y', 'n']:
                    break
    if (save_results == 'y') or args.overwrite or not os.path.isfile(raw_lines_path):
        final_report.lines.to_csv(raw_lines_path, index=True)
