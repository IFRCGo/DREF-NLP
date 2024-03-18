import yaml
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFINITIONS_DIR = os.path.join(ROOT_DIR, 'ea_parsing', 'definitions')

LESSONS_LEARNED_TITLES = yaml.safe_load(open(os.path.join(DEFINITIONS_DIR, 'lessons_learned_titles.yml')))
SECTORS = yaml.safe_load(open(os.path.join(DEFINITIONS_DIR, 'sectors.yml')))
ABBREVIATIONS = yaml.safe_load(open(os.path.join(DEFINITIONS_DIR, 'abbreviations.yml')))

BULLETS = [
    '•', '●', '▪', '-', 'o',
    '❖', '◆', '♢', '◇', '⬖',
    u'\uf0b7', u'\u2023', u'\u2043', u'\u204C', u'\u204D', u'\u2219',
    u'\u25CB', u'\u25CF', u'\u25D8', u'\u25E6', u'\u2619', u'\u2765',
    u'\2767', u'\u29BE', u'\u29BF', u'\u25C9', u'\uf0a7', u'\uf0d8',
    u'\uf076'
]