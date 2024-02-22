import yaml
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFINITIONS_DIR = os.path.join(ROOT_DIR, 'ea_parsing', 'definitions')

LESSONS_LEARNED_TITLES = yaml.safe_load(open(os.path.join(DEFINITIONS_DIR, 'lessons_learned_titles.yml')))
SECTORS = yaml.safe_load(open(os.path.join(DEFINITIONS_DIR, 'sectors.yml')))
ABBREVIATIONS = yaml.safe_load(open(os.path.join(DEFINITIONS_DIR, 'abbreviations.yml')))