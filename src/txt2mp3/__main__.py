import sys, os, io
import argparse
import tempfile
import shutil
import json

import tqdm
# import nltk
from gtts import gTTS, lang

SEGMENT_SIZE_MAX = 5000
SEGMENT_SIZE_MIN = 100

parser = argparse.ArgumentParser(
    description='Uses Google TTS to read up a long text file and split to pieces.'
)

parser.add_argument(
    '--input',
    '-i',
    dest='input_file',
    type=str,
    help='Input txt file.',
    required=True
)

parser.add_argument(
    '--output',
    '-o',
    dest='output_file',
    type=str,
    help='Output file name.',
    required=True
)

parser.add_argument(
    '--language',
    '-l',
    dest='language',
    type=str,
    default='en',
    help='Language to be used.',
)

parser.add_argument(
    '--segment-size',
    '-s',
    dest='segment_size',
    default=5000,
    help=f'Sets maximum length of segments to be taken. Between {SEGMENT_SIZE_MIN} and {SEGMENT_SIZE_MAX}.',
)

parser.add_argument(
    '--list-languages',
    dest='is_list_all_languages',
    action='store_true',
    default=False,
    help='List all available languages.',
)

args = parser.parse_args()



if __name__ == '__main__':
    if args.is_list_all_languages:
        for (code, name) in lang.tts_langs().items():
            print(f'{code}: {name}')
        exit(0)

    if not os.path.exists(args.input_file):
        print(f'File {args.input_file} does not exists')
        exit(-1)

    segment_size = args.segment_size if args.segment_size >= SEGMENT_SIZE_MIN  else SEGMENT_SIZE_MIN if args.segment_size <= SEGMENT_SIZE_MAX  else SEGMENT_SIZE_MAX 
    segments = []
    with open(args.input_file, 'rt') as fp:
        last_sentence = ''
        last_segment = ''
        for line in fp.readlines():
            words = line.split() #nltk.word_tokenize(line)
            # Empty line, split segment 
            if not words:
                if last_segment != '':
                    segments.append(last_segment.strip())
                    last_segment = ''
                
                if last_sentence != '':
                    segments.append(last_sentence.strip())
                    last_sentence = ''

            for word in words: 
                # TODO Filter stuff here
                # TODO Replace stuff here
                last_sentence += " " + word
                if sum(word.endswith(delimiter) for delimiter in ['.', '!', '?']) == 1:
                    if len(last_segment) + len(last_sentence) > segment_size:
                        segments.append(last_segment.strip())
                        last_segment = ''
                    last_segment += " " + last_sentence
                    last_sentence = ''
        segments.append(last_segment)
    
    tmp_files = []
    
    for segment in tqdm.tqdm(segments, desc="Calling TTS srervice"):
        if len(segment) > 0:
            tts = gTTS(segment, lang=args.language) 
            with tempfile.NamedTemporaryFile('wb', delete=False,suffix='.mp3') as tmp:
                tts.write_to_fp(tmp)
                tmp_files.append(tmp.name)

    if os.path.exists(args.output_file):
        os.unlink(args.output_file)
    with open(args.output_file, 'wb') as fp:
        for tmp_file in tqdm.tqdm(tmp_files, desc="Joining segments"):
            with open(tmp_file, 'rb') as tmp:
                shutil.copyfileobj(tmp, fp)
            os.unlink(tmp_file)

