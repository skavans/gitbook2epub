import re
import sys
import time
from uuid import uuid4

import httpx
from ebooklib import epub
from lxml import html, etree


client = httpx.Client()


def _outerhtml(element, book, dom=None):
    _html = etree.tostring(element, encoding='unicode', method='html', with_tail=True)

    _html = re.sub(r'class="[^"]+"', '', _html)
    _html = re.sub(r'style="[^"]+"', '', _html)
    _html = re.sub(r'id="[^"]+"', '', _html)
    _html = re.sub(r'href="#[^"]*"', '', _html)

    _html = re.sub(r'<button.*?</button>', '', _html)
    _html = re.sub(r'<svg.*?</svg>', '', _html)
    _html = re.sub(r'<math.*?</math>', '', _html)

    for elem_to_remove in ('div', 'pre'):
        _html = re.sub(rf'</?{elem_to_remove}[^>]*>', '', _html)

    # remove empty paragraphs
    _html = re.sub(r'<p[^>]*>\s*</p>', '', _html, flags=re.DOTALL)

    # codeblock fix
    def _fix_codeblock(codeblock):
        is_inline = '<span' not in codeblock.group(0)

        code = re.sub(r'<.*?>', '', codeblock.group(0)).lstrip()

        if not is_inline:
            return f"""<pre class="code-block"><code>\n{code}\n</code></pre>"""
        else:
            return f"""<code class="code-inline">{code}</code>"""
    _html = re.sub('<code.*?</code>', _fix_codeblock, _html, flags=re.DOTALL)

    # images processing
    def _process_images(image):
        image = image.group(0)
        image = re.sub(r'srcset=".*?"', '', image)
        src = re.search(r'src="(.*?)"', image)
        if not src:
            src = re.search(r"src='(.*?)'", image)
        link = src.group(1)
        image_content = client.get(link.replace('&amp;', '&')).content
        img_id = str(uuid4())
        img = epub.EpubImage(
            uid=img_id,
            file_name=f"static/{img_id}",
            # media_type="image/png",
            content=image_content,
        )
        book.add_item(img)
        return image.replace(link, f"static/{img_id}")
    _html = re.sub(r'<img.*?>', _process_images, _html, flags=re.DOTALL)

    return _html


def main():
    gitbook_start_url = sys.argv[1]
    book_title = sys.argv[2]
    book_author = sys.argv[3]
    out_file = sys.argv[4]

    gitbook_start_url = gitbook_start_url.rstrip('/')
    gitbook_root = 'https://' + gitbook_start_url.split('/')[2]
    content = client.get(gitbook_start_url, follow_redirects=True).text
    dom = html.fromstring(content)

    book = epub.EpubBook()

    book.set_identifier(str(uuid4()))
    book.set_title(book_title)
    book.set_language('en')
    book.add_author(book_author)
    book.toc = []
    book.spine = ['nav']

    style = epub.EpubItem(
        uid="style",
        file_name="style/style.css",
        media_type="text/css",
        content='''
            .code-block {
                font-family: 'Courier New', monospace; 
                font-size: 0.7em; 
                background-color: #f5f5f5;
                padding: 0.5em;
                margin: 1em 0;
                white-space: pre-wrap;
                word-wrap: break-word;
                line-height: 1.2;
                text-align: left;
            }

            .code-inline {
                font-family: 'Courier New', monospace; 
                background-color: #f5f5f5;
                white-space: pre-wrap;
                word-wrap: break-word;
            }
        '''.encode('utf-8')
    )
    book.add_item(style)

    chapters_count = 0

    # searching for the non-hidden links in the left navigation bar
    # they will be the chapters' roots
    for first_layer_link in dom.xpath('//aside//a[@insights][not(ancestor::div[contains(@style, "display:none")])]'):
        
        chapters_count += 1
        
        content_links = [first_layer_link.get('href')]
        # now searching for the links in the sibling hidden div
        # they will be the subchapters
        for subchapter_link in first_layer_link.xpath('./following-sibling::div[contains(@style, "display:none")]//li//a[@insights]'):
            content_links.append(subchapter_link.get('href'))

        chapter_content = '<html><body>'
        for i, cl in enumerate(content_links):
            while True:
                try:
                    content = client.get(f'{gitbook_root}{cl}').text
                    dom = html.fromstring(content)
                    
                    # processing templates
                    def _process_template(tpl: re.Match):
                        tpl_id = tpl.group(1)
                        repl_id = re.search(fr'\$RC\("{tpl_id}","(.*?)"\)', content)
                        if not repl_id:
                            repl_id = re.search(fr'\$RS\("([^"]+)","{tpl_id}"\)', content)
                        repl_id = repl_id.group(1)
                        repl = dom.cssselect(f'div[id="{repl_id}"]')[0]
                        return etree.tostring(repl, encoding='unicode', method='html', with_tail=True)

                    while '<template' in content:
                        content = re.sub(r'<template id="(.*?)"></template>', _process_template, content)
                        content = content.replace('<div hidden', '<div')
                    dom = html.fromstring(content)

                    if 0 == i:
                        title = dom.cssselect('main header h1')[0].text_content()

                    chapter_content += _outerhtml(dom.cssselect('main header h1')[0], book)
                    chapter_content += _outerhtml(dom.cssselect('main > *:nth-child(2)')[0], book)
                except Exception as e:
                    print(e)
                    time.sleep(5)
                else:
                    break
        chapter_content += '</body></html>'
        
        fname = str(uuid4()) + '.xhtml'
        chapter = epub.EpubHtml(title=title, file_name=fname, lang='en')
        chapter.set_content(chapter_content)
        chapter.add_item(style)
        book.add_item(chapter)

        book.toc.append(epub.Link(fname, title, fname))
        book.spine.append(chapter)

        print(f'[+] Chapter {chapters_count}: {title}')

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(out_file, book)


if __name__ == "__main__":
    main()
