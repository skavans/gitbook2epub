# GitBook2EPUB

This is a simple tool for parsing GitBook online books into EPUB offline ones.
It tries to preserve the navigation structure (mostly), text formatting, links, codeblocks and images.

The software is provided as is. I developed it for my own purpose and tested it only on a very few gitbooks.
If you want to add/fix something – feel free to submit pull requests.

## Installation

Download the repo and install its python dependencies with
```bash
pip3 install -r requirements.txt
```

## Usage

Run it with
```bash
python3 main.py <gitbook_first_page_url> <title> <author> <epub_out_filename>
```
for instance
```bash
python3 main.py https://basarat.gitbook.io/typescript Typescript TestAuthor typescript.epub
```
