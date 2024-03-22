import ea_parsing.definitions
from ea_parsing.utils import strip_non_alpha, remove_filler_words, generate_sentence_variations


class Sectors:
    def __init__(self):
        """
        """
        self.sectors = self._process_sectors(
            sectors=ea_parsing.definitions.SECTORS,
            abbreviations=ea_parsing.definitions.ABBREVIATIONS
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
        for sector_name, titles in sectors.items():

            # Add the sector name to the titles
            sector_name_base = strip_non_alpha(sector_name).lower()
            if titles is None:
                sectors_processed[sector_name] = [sector_name_base]
            else:

                # Loop through titles and add base text
                sectors_processed[sector_name] = [
                    strip_non_alpha(title).lower()
                    for title in titles
                ]
                # Add sector title
                if sector_name_base not in titles:
                    sectors_processed[sector_name].append(sector_name_base)

        return sectors_processed

    def _add_abbreviations(self, sectors, abbreviations):
        """
        """
        sectors_with_abbs = {}
        for sector_name, titles in sectors.items():
            sectors_with_abbs[sector_name] = []
            for title in titles:
                sector_options = generate_sentence_variations(
                    sentence=title,
                    abbreviations=abbreviations
                )
                sectors_with_abbs[sector_name] += sector_options

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
            if text_base != prefix:
                if text_base.startswith(prefix):
                    text_base = text_base[len(prefix):].strip()

        # First, check if there is an exact match with the titles
        for sector_name, titles in self.sectors.items():
            for title in titles:
                if text_base == title:
                    return sector_name, 1

        # Next, check if the title is any title plus filler words
        for sector_name, titles in self.sectors.items():
            for title in titles:
                if remove_filler_words(text_base) == remove_filler_words(title):
                    return sector_name, 1

        return None, 0
