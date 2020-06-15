import requests
from bs4 import BeautifulSoup as bs
from bs4 import Comment
import argparse
import re
from pathlib import Path
from util import compress
import json
from bookcreator import BookCreator

headers = {"user-agent:": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36"}

blacklist_patterns = [
    r'^[\W\D]*(volume|chapter)[\W\D]+\d+[\W\D]*$',
]
bad_tags = [
    'noscript', 'script', 'iframe', 'form', 'hr', 'img', 'ins',
    'button', 'input', 'amp-auto-ads', 'pirate'
]

def is_blacklisted(text):
    if len(text.strip()) == 0:
        return True
    for pattern in blacklist_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def is_valid(arg):
    pattern = r"^https://kobatochan\.com/(?:korean-novels|japanese-novels|chinese-novels|original-works)/(.+?)/$"
    match = re.match(pattern, arg)
    return match[1] if match else None

def get_soup(session, url):
    response = session.get(url)
    if response.status_code != 200:
        print(f"failed to get {url}: {response.status_code}")
        return None
    response.encoding = 'utf-8'
    return bs(response.text, 'html.parser')

def get_info(soup):   
    title_elem = soup.select_one("h1.entry-title > a")
    title = title_elem.text if title_elem else None
    
    author_pattern = r'Author:\s(.+?)'
    content = soup.select_one('div.entry_content')
    matches = soup.find_all("strong", text=re.compile(author_pattern))
    author = matches[0].text.replace("Author: ", "") if matches else None

    return {'title' : title, 'author': author}

def get_cover(novel_path, soup):
    cover_url = soup.select_one('div.entry-content > p > img')
    if not cover_url:
        return
    cover_url = cover_url['src']
    cover_path = novel_path.joinpath('cover.jpg')
    response = requests.get(cover_url)
    if response.status_code != 200:
        return
    with cover_path.open('wb+') as f:
        f.write(response.content)
    
def get_chapters(soup):
    chapters = []
    chapter_urls = soup.select("div.entry-content > p > a")
    for u in chapter_urls:
        chapters.append((u.text, u['href']))
    return chapters

def clean_contents(div):
    if not div:
        return div
    div.attrs = {}
    for tag in div.findAll(True):
        if isinstance(tag, Comment):
            tag.extract()
        elif tag.name == 'br':
            next_tag = getattr(tag, 'next_sibling')
            if next_tag and getattr(next_tag, 'name') == 'br':
                tag.extract()
        elif tag.name in bad_tags:
            tag.extract()
        elif not tag.text.strip():
            tag.extract()
        elif is_blacklisted(tag.text):
            tag.extract()
        elif hasattr(tag, 'attrs'):
            tag.attrs = {}
    return div

def download_chapters(novel_path, session, chapters):
    for i, (title, url) in enumerate(chapters):
        print(f"downloading chapter {i}")
        soup = get_soup(session, url)
        title = title if title else f"Chapter {i}"
        content = soup.select_one("div.entry-content")
        content = clean_contents(content)
        body = content.select('p')
        body = [str(p) for p in body if p.text != "/"]
        k =  '<p>' + '</p><p>'.join(body) + '</p>'
        filename = f"{i}".zfill(5) + ".json"
        volume = max([1, 1 + (i - 1) // 100])
        filepath = novel_path.joinpath(str(volume), filename)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        jdata = {"body": compress(k), 'chapter_no': i, 'chapter_title': title}
        with filepath.open('w+', encoding='utf-8') as f:
            json.dump(jdata, f, separators=(',', ':'))

def count_chapters(novel_path):
    return len(list(novel_path.glob('**/*.json')))

def main():
    parser = argparse.ArgumentParser(description='download novels from kobatochan')
    parser.add_argument('url', metavar='U', type=str, help='url to novel')
    args = parser.parse_args()
    novel_id = is_valid(args.url)
    if not novel_id:
        raise argparse.ArgumentTypeError("%s is not supported" % args.url)

    novel_path = Path("novels", novel_id)
    novel_path.mkdir(parents=True, exist_ok=True)
    
    print(args)
    session = requests.Session()
    session.headers.update(headers)
    soup = get_soup(session, args.url)
    get_cover(novel_path, soup)
    infos = get_info(soup)
    chapters = get_chapters(soup)

    chap_count = count_chapters(novel_path)
    if chap_count != len(chapters):
        download_chapters(novel_path, session, chapters)

    for volume in novel_path.iterdir():
        if volume.is_dir():
            bc = BookCreator(novel_id, infos['title'], volume.name, volume, infos['author'])
            bc.start()


if __name__ == "__main__":
    main()