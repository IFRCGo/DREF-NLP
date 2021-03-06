import os

from datasets.bert_processors.abstract_processor import BertProcessor, InputExample


class IFRCProcessor(BertProcessor):
    NAME = 'IFRC'
    NUM_CLASSES = 46
    IS_MULTILABEL = True
    
    def get_train_examples(self, data_dir):
        return self._create_examples(
            self._read_tsv(os.path.join(data_dir, 'IFRC', 'train.tsv')), 'train')

    def get_dev_examples(self, data_dir):
        return self._create_examples(
            self._read_tsv(os.path.join(data_dir, 'IFRC', 'dev.tsv')), 'dev')

    def get_test_examples(self, data_dir):
        return self._create_examples(
            self._read_tsv(os.path.join(data_dir, 'IFRC', 'test.tsv')), 'test')

    def _create_examples(self, lines, set_type):
        examples = []
        for (i, line) in enumerate(lines):
            if i == 0:
                continue
            guid = '%s-%s' % (set_type, i)
            text_a = line[1]
            label = line[0]
            examples.append(
                InputExample(guid=guid, text_a=text_a, text_b=None, label=label))
        return examples