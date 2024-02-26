"""
"""
from functools import cached_property
import ea_parsing.definitions
from ea_parsing.utils import strip_non_alpha, strip_filler_words, phrase_in_sentence, replace_phrases_in_sentence, generate_sentence_variations


class Sectors:
    def __init__(self):
        """
        """
        self.sectors = self._process_sectors(
            sectors = ea_parsing.definitions.SECTORS,
            abbreviations = ea_parsing.definitions.ABBREVIATIONS
        )


    def _process_sectors(self, sectors, abbreviations):
        """
        """
        sectors = self._strip_characters(sectors)
        sectors = self._add_abbreviations(sectors, abbreviations)
        return sectors

    
    def _strip_characters(self, sectors):
        # Process - add sector name, and swap common words
        sectors_processed = {}
        for sector_name, details in sectors.items():
            sectors_processed[sector_name] = {}

            # Add the sector name to the titles
            sector_name_base = strip_non_alpha(sector_name).lower()
            if details is None:
                sectors_processed[sector_name] = {
                    'titles': [sector_name_base],
                    'keywords': []
                }
            else:
                if 'titles' in details:

                    # Loop through titles and add base text
                    sectors_processed[sector_name]['titles'] = [
                        strip_non_alpha(title).lower() 
                        for title in details['titles']
                    ]
                    # Add sector title
                    if sector_name_base not in details['titles']:
                        sectors_processed[sector_name]['titles'].append(sector_name_base)

                else:
                    sectors_processed[sector_name]['titles'] = [sector_name_base]

                # Loop through keywords and add base text
                if 'keywords' in details:
                    sectors_processed[sector_name]['keywords'] = [
                        strip_non_alpha(keyword).lower() 
                        for keyword in details['keywords']
                    ]
                else:
                    sectors_processed[sector_name]['keywords'] = []

        return sectors_processed


    def _add_abbreviations(self, sectors, abbreviations):
        """
        """
        sectors_with_abbs = {}
        for sector_name, details in sectors.items():
            sectors_with_abbs[sector_name] = {
                'titles': [], 
                'keywords': details['keywords']
            }
            for title in details['titles']:
                sector_options = generate_sentence_variations(
                    sentence=title, 
                    abbreviations=abbreviations
                )
                sectors_with_abbs[sector_name]['titles'] += sector_options

        return sectors_with_abbs


    def get_similar_sector(self, text):
        """
        Get the sector that is most similar to the given text.
        Return the sector title and a score representing the similarity.
        """
        text_base = strip_non_alpha(text).lower()

        # Remove any prefix text
        prefixes = ['strategies for implementation']
        for prefix in prefixes:
            if text_base!=prefix:
                if text_base.startswith(prefix):
                    text_base = text_base[len(prefix):].strip()

        # First, check if there is an exact match with the titles
        for sector_name, details in self.sectors.items():
            for title in details['titles']:
                if text_base == title:
                    return sector_name, 1

        # Next, check if the title is any title plus filler words 
        for sector_name, details in self.sectors.items():
            for title in details['titles']:
                if strip_filler_words(text_base) == strip_filler_words(title):
                    return sector_name, 1

        # Next, check if there is an exact match with any keywords
        for sector_name, details in self.sectors.items():
            for keyword in details['keywords']:
                if text_base == keyword:
                    return sector_name, 0.9

        # Next, check how many words in the text are covered by each sector and sector keywords
        proportion_text_covered_by_sector = {}
        for sector_name, details in self.sectors.items():
            keywords = details['keywords']
            
            # Extract filler words and keywords
            text_without_fillers = strip_filler_words(text_base)
            text_without_keywords = replace_phrases_in_sentence(keywords, '', text_without_fillers).strip()

            # Get the proportion of words covered
            if text_without_fillers == text_without_keywords:
                proportion_text_covered_by_sector[sector_name] = 0
            elif not text_without_keywords:
                proportion_text_covered_by_sector[sector_name] = 1
            else:
                number_words_covered = len(text_without_fillers.split(' ')) - len(text_without_keywords.split(' '))
                proportion_text_covered_by_sector[sector_name] = number_words_covered/len(text_without_fillers.split(' '))

        # Return the best matching sector
        max_sector = max(proportion_text_covered_by_sector, key=lambda x: 0 if proportion_text_covered_by_sector[x]!=proportion_text_covered_by_sector[x] else proportion_text_covered_by_sector[x])
        max_proportion = proportion_text_covered_by_sector[max_sector]

        if max_proportion > 0:
            return max_sector, max_proportion

        return None, 0