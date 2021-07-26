import sys
import os
import io
import argparse
import tempfile
import shutil
import json
import time
import zipfile

import logging

import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from gtts import gTTS, lang

SEGMENT_SIZE_MAX = 5000
SEGMENT_SIZE_MIN = 100

MAX_WAIT = 128

AUTO_SAVE_COUNT = 100

LOG = logging.getLogger(__name__)

parser = argparse.ArgumentParser(
    description='Uses Google TTS to read up a long text file and split to pieces.'
)

parser.add_argument(
    '--input',
    '-i',
    dest='input_file',
    type=str,
    help='Input txt file.',
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

parser.add_argument(
    '--resume',
    '-r',
    dest='recover_file',
    default='',
    help='Load partial results from a file to continue interrupted generation.',
)

args = parser.parse_args()


def do_tts(*args, **kwargs):
    wait_time = 1
    for i in range(MAX_WAIT):
        try:  
            tts=gTTS(*args, **kwargs)             
            with tempfile.NamedTemporaryFile('wb', delete=False, suffix='.mp3') as tmp:
              tts.write_to_fp(tmp)
              return tmp.name
        except:
            LOG.info(f'Wait for {wait_time}')
            time.sleep(wait_time)
            wait_time *= 2
    raise RuntimeError()


def pack_archive(data, recover_file_name, delete_files=True):
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.json') as tmp:
        data_to_write = []
        
        for d in data:
            dd = {}
            dd['text'] = d['text']
            if 'mp3' in d:
                dd['mp3'] = os.path.basename(d['mp3'])
            data_to_write.append(dd)

        json.dump(data_to_write, tmp)
        json_filename=tmp.name

    if os.path.exists(recover_file_name):
        os.unlink(recover_file_name)

    with zipfile.ZipFile(recover_file_name, mode='w') as recover_file:
        recover_file.write(json_filename, 'recover.json')
        os.unlink(json_filename)
        for d in tqdm.tqdm(data, desc='Packing'):
            if 'mp3' in d and os.path.exists(d['mp3']):
                recover_file.write(d['mp3'], arcname=os.path.basename(d['mp3']))
                if delete_files:
                    os.unlink(d['mp3'])
    LOG.info(f'Packing OK {recover_file_name}')


def unpack_archive(recover_file_name):
    extract_dir = tempfile.gettempdir()
    with zipfile.ZipFile(recover_file_name, 'r') as recover_file:
        with recover_file.open('recover.json') as f:
            data=json.load(f)
        for d in tqdm.tqdm(data, desc='Unpacking'):
            if 'mp3' in d:
                recover_file.extract(d['mp3'], path=extract_dir)
                d['mp3'] = os.path.join(extract_dir, d['mp3'])
    LOG.info(f'Unpacking OK {recover_file_name}')
    return data



if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,format='[%(levelname)s]: %(message)s')

    if args.is_list_all_languages:
        for (code, name) in lang.tts_langs().items():
            print(f'{code}: {name}')
        exit(0)

    is_read_input=args.input_file != '' and args.recover_file==''
    is_read_recover=args.input_file == '' and args.recover_file != ''

    if not is_read_input and not is_read_recover:
        LOG.error('-i or -r must be specified.')
        parser.print_help()
        exit(-1)

    recover_file=args.recover_file if args.recover_file != '' else args.output_file + '.resume'

    if is_read_input and not os.path.exists(args.input_file):
        LOG.error(f'File {args.input_file} does not exists')
        exit(-1)

    if is_read_recover and not os.path.exists(recover_file):
        LOG.error(f'Recover file {args.input_file} does not exists')
        exit(-1)

    segment_size=args.segment_size if args.segment_size >= SEGMENT_SIZE_MIN else SEGMENT_SIZE_MIN if args.segment_size <= SEGMENT_SIZE_MAX else SEGMENT_SIZE_MAX

    segments=[]
    if os.path.exists(recover_file):
        segments=unpack_archive(recover_file)
    else:
        with open(args.input_file, 'rt') as fp:
            last_sentence=''
            last_segment=''
            for line in fp.readlines():
                words=line.split()  # nltk.word_tokenize(line)
                # Empty line, split segment
                if not words:
                    if last_segment != '':
                        segments.append({'text': last_segment.strip()})
                        last_segment=''

                    if last_sentence != '':
                        segments.append({'text': last_sentence.strip()})
                        last_sentence=''

                for word in words:
                    # TODO Filter stuff here
                    # TODO Replace stuff here
                    last_sentence += ' ' + word
                    if sum(word.endswith(delimiter) for delimiter in ['.', '!', '?']) == 1:
                        if len(last_segment) + len(last_sentence) > segment_size:
                            segments.append({'text': last_segment.strip()})
                            last_segment=''
                        last_segment += ' ' + last_sentence
                        last_sentence=''
            segments.append({'text': last_segment.strip()})

        pack_archive(segments, recover_file)

    with logging_redirect_tqdm():
        try:
            auto_save_count=0
            for segment in tqdm.tqdm(segments, desc='Calling TTS srervice'):
                text=segment['text']
                if len(text) > 0 and 'mp3' not in segment:
                    segment['mp3']=do_tts(text, lang=args.language)
                    if auto_save_count >= AUTO_SAVE_COUNT:
                        LOG.info('Autosave...')
                        pack_archive(segments, recover_file, delete_files=False)
                        auto_save_count=0

                    auto_save_count += 1
        except KeyboardInterrupt:
            LOG.info('Exiting...')
            pack_archive(segments, recover_file)
            exit(0)
        except:
            LOG.exception('Exiting...')
            pack_archive(segments, recover_file)
            exit(-1)

    pack_archive(segments, recover_file)

    LOG.info('TTS Done')

    if os.path.exists(args.output_file):
        os.unlink(args.output_file)
    with open(args.output_file, 'rb') as fp:
        for segment in tqdm.tqdm(segments, desc='Joining segments'):
            tmp_file=segment['mp3']
            with open(tmp_file, 'wb') as tmp:
                shutil.copyfileobj(tmp, fp)
            os.unlink(tmp_file)

    LOG.info('Joining MP3 Done')

    if os.path.exists(recover_file):
        os.unlink(recover_file)
