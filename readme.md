# txt2mp3
Quick and dirty tool to convert longer texts to mp3 using Google TTS

## Installing

In your own enviroment issue the following commands:

```
pip install -r requirements.txt
python setup.py build
python setup.py install
```

## Usage

```
python -m txt2mp3 -i input.txt -o output.txt
```

Use `-h` for print internal help.

## Know issues
- Setup script should be able to install requirements
- Lack of [preprocessing and tokenizing](https://gtts.readthedocs.io/en/latest/tokenizer.html#id3) support
- Sentence and section splitting may be broken 
- Does not support ripping off segmenting elements such as line of `---` and `===`