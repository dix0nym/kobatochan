#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BookCreator for novels"""
import json
import logging
import os
import re
from pathlib import Path

from bs4 import BeautifulSoup as bs
from ebooklib import epub
import util

BOOK_PATH = '_book'


class BookCreator:
    """BookCreator for novels"""

    def __init__(self, novel_id, novel_name, volume_no, input_path, author, logger=None):
        """init"""
        self.novel_id = novel_id
        self.input_path = input_path
        self.volume_no = volume_no
        self.novel_name = novel_name
        self.book = epub.EpubBook()
        self.auther = author if author else 'Unkown'
        self.logger = logger or logging.getLogger(__name__)

    def start(self):
        """start working"""
        self.logger.info("Building %s - V %s", self.novel_id, self.volume_no)
        self.book.set_identifier(self.novel_id + self.volume_no)
        self.book.set_language('en')
        self.add_cover()
        self.add_styles()
        self.add_fonts()
        self.create_book()
        self.save()

    # end def

    def clean_body(self, content, chapter_title):
        """br -> p, remove all tags except valid_tags, remove all elements containing 'chapter'"""
        lines = [
            line for line in re.split(r'<(/|)br(\s|)(/|)>', content)
            if len(line) > 0 and not line.isspace()
        ]
        cleaned = "</p><p>".join(lines)
        soup = bs(cleaned, 'lxml')
        for elem in soup(text=re.compile(r'chapter', re.IGNORECASE)):
            # dont remove if more than 5% of text
            if len(elem.parent.text) >= 0.05 * len(soup.text):
                continue
            elem.parent.extract()

        for match in soup.findAll():
            if match.text == "" or match.name not in ["p", "strong", "b", "i"]:
                match.replaceWithChildren()
        return "<h4>{}</h4><hr/><div id=\"content\">{}</div>".format(
            chapter_title, soup.decode_contents())

    def create_chapter(self, chapter_file):
        """create chapter from json-file"""
        try:
            item = json.load(open(chapter_file, 'r'))
            xhtml_file = "chap_{}.xhtml".format(str(item['chapter_no']).zfill(4))
            if not item["body"]:
                self.logger.error("body is empty (file: %s)", chapter_file)
                return epub.EpubHtml()
            # decompress
            decompressed = util.decompress(item["body"])
            if util.isbase64(decompressed):
                self.logger.error("still base64 encoded body after decompressing? (file: %s)", chapter_file)
                return epub.EpubHtml()
            body = self.clean_body(decompressed, item['chapter_title']) or decompressed
            chapter = epub.EpubHtml(
                lang='en',
                file_name=xhtml_file,
                uid=str(item['chapter_no']),
                content=body,
                title=item['chapter_title'])
            chapter.add_link(
                href="../Styles/ChapterStyle.css",
                rel='stylesheet',
                type='text/css')
            # end for
            return chapter
        except json.decoder.JSONDecodeError as e:
            self.logger.error("file:%s\nmsg:%s" % (chapter_file, e))
            return epub.EpubHtml()

    # end def

    def create_book(self):
        """create book"""
        self.logger.debug("Building: %s", self.input_path)
        contents = []
        for file_name in sorted(os.listdir(self.input_path)):
            chapter_file = os.path.join(self.input_path, file_name)
            chapter = self.create_chapter(chapter_file)
            self.book.add_item(chapter)
            contents.append(chapter)
        # end for
        self.add_metadata(contents)

    # end def

    def add_metadata(self, contents):
        """add metadata to book"""
        self.logger.debug("Adding metadata")
        self.book.spine = ['cover', 'nav'] + contents
        self.book.add_author(self.auther)
        self.book.set_title("{} Vol. {}".format(self.novel_name,
                                                self.volume_no.zfill(2)))
        self.book.toc = contents
        self.book.add_item(epub.EpubNav())
        self.book.add_item(epub.EpubNcx())

    # end def

    def add_styles(self):
        """add styles in folder to book"""
        self.logger.debug("Adding styles")
        for idx, style_file in enumerate(os.listdir("styles")):
            style = open("styles/" + style_file, 'r').read()
            nav_css = epub.EpubItem(
                uid="style_nav" + str(idx),
                file_name="style/" + style_file,
                media_type="text/css",
                content=style)
            self.book.add_item(nav_css)
            self.logger.debug("Adding css %s", style_file)
        # end for

    # end def

    def add_fonts(self):
        """add fonts in folder to book"""
        self.logger.debug("Adding fonts")
        for idx, font in enumerate(os.listdir("fonts")):
            font_raw = open("fonts/" + font, 'rb').read()
            nav_font = epub.EpubItem(
                uid="font_nav" + str(idx),
                file_name="fonts/" + font,
                media_type="application/font-sfnt",
                content=font_raw)
            self.book.add_item(nav_font)
            self.logger.debug("Adding font %s", font)
        # end for

    # end def

    def add_cover(self):
        """add cover if exists to book"""
        cover_path = os.path.join(
            Path(self.input_path).parent.as_posix(), "cover.jpg")
        if os.path.isfile(cover_path):
            self.logger.debug("Set cover %s", cover_path)
            cover_template = open("template/cover.xhtml", 'rb').read().replace(
                b'\r', b'')
            self.book.set_template("cover", cover_template)
            self.book.set_cover("cover.jpg", open(cover_path, 'rb').read())
            cover_page = self.book.get_item_with_href("cover.xhtml")
            cover_page.is_linear = True
            cover_page.add_link(
                href="../Styles/Cover.css", rel='stylesheet', type='text/css')
            # self.book.set_cover("cover.jpg", open(cover_path, 'rb').read())
        # end if

    # end def

    def save(self):
        """save book to file"""
        name = util.get_valid_fs_name(self.novel_name)
        output_path = os.path.join(BOOK_PATH, name)
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        # end if
        file_name = "{}_v{}.epub".format(name.replace("-", "_"), self.volume_no.zfill(2))
        file_path = os.path.join(output_path, file_name)
        self.logger.info("Creating: %s", file_path)
        epub.write_epub(file_path, self.book, {})

    # end def


# end class
