# -*- coding = utf-8 -*-

# Script to crawl poems from gushiwen.cn

from bs4 import BeautifulSoup
import re
import requests
import time
import os


# Remove special format symbols
def clear_data(text):
    # Remove \xa0, \t, \u3000 format spaces
    text = re.sub('\s', '', text)
    return text


# Parse and save individual poem content
def crawl_poem(html, header, dir_name, poem_title, flog):
    # Open URL
    request = requests.get(url=html, headers=header)
    time.sleep(0.5)

    # Build BeautifulSoup parsing object
    bs = BeautifulSoup(request.text, 'lxml')

    # For poem pages (shiwenv_*.aspx), extract content from div.contson
    # IMPORTANT: There are multiple div.contson on page (sidebar, related content, etc.)
    # We need the FIRST one in the main content area
    # The correct selector is: body > div.main3 > div.left > div.sons > div.cont > div.contson
    main_contson = bs.select_one("div.main3 div.left div.sons div.cont div.contson")

    if not main_contson:
        # Fallback: try the first contson with an ID (main content usually has ID)
        all_contson = bs.select("div.contson[id]")
        if all_contson:
            main_contson = all_contson[0]

    if main_contson:
        # Check if it has <p> tags or direct text
        paragraphs = main_contson.select("p")

        if paragraphs:
            # Method 1: Content in <p> tags
            f1 = open(os.path.join(dir_name, "text.txt"), "w", encoding="utf-8")
            for p in paragraphs:
                text = p.get_text().strip()
                if text:
                    text = clear_data(text) + '\n'
                    f1.write(text)
            f1.close()
            print(f"    Saved {len(paragraphs)} paragraphs")
            # Write to log
            flog.write(f"###{poem_title}###\n")
            flog.flush()
        else:
            # Method 2: Content directly with <br/> tags
            text = main_contson.get_text().strip()
            if text:
                f1 = open(os.path.join(dir_name, "text.txt"), "w", encoding="utf-8")
                f1.write(clear_data(text) + '\n')
                f1.close()
                print(f"    Saved poem content")
                # Write to log
                flog.write(f"###{poem_title}###\n")
                flog.flush()
            else:
                print(f"    No content found")
    else:
        print(f"    No content found")


# Parse a single page of poems
def crawl_poems_on_page(bs, header, base_dir_name, page_num, total_poems_so_far, last_poem, flog):
    # Extract poem links and titles
    poem_items = bs.select("div.sons div.cont")

    poems_on_page = 0
    skip_mode = (last_poem is not None)  # If we have a last_poem, we're in resume mode

    for item in poem_items:
        # Extract poem title and link
        title_link = item.select_one("p a")
        if not title_link:
            continue

        poem_url = title_link.get('href', '')
        poem_title = title_link.get_text().strip()

        if not poem_url or not poem_title:
            continue

        # Handle special characters in filename
        sanitized_title = poem_title.replace('/', '&') if '/' in poem_title else poem_title

        # Resume logic: skip until we find the last poem
        if skip_mode:
            if sanitized_title == last_poem:
                print(f"[RESUME] Found last crawled poem: {poem_title}, resuming from next...")
                skip_mode = False
            continue

        poems_on_page += 1

        # Handle relative URL
        if not poem_url.startswith('http'):
            poem_url = "https://www.gushiwen.cn" + poem_url

        # Create poem directory
        dir = os.path.join(base_dir_name, sanitized_title)
        if not os.path.exists(dir):
            os.makedirs(dir)

        print(f"[{total_poems_so_far + poems_on_page}] {poem_title}")

        # Crawl specific poem content
        crawl_poem(poem_url, header, dir, sanitized_title, flog)

    return poems_on_page, skip_mode


# Read log file to get the last crawled poem
def read_log():
    log_file = 'log/crawl_poems_log.txt'
    if not os.path.exists(log_file):
        return None

    flog = open(log_file, 'r', encoding="utf-8")
    log = flog.read()
    flog.close()

    # Read the last crawled poem
    last_poem = ""
    if len(re.findall('###(.*)###', log)) > 0:
        last_poem = re.findall('###(.*)###', log)[-1]
        return last_poem
    else:
        return None


# Parse all pages of poem listings
def crawl_poems_list(baseurl, header, base_dir_name, last_poem, flog):
    current_url = baseurl
    page_num = 1
    total_poems = 0
    skip_mode = (last_poem is not None)

    while current_url:
        print(f"\n=== Page {page_num} ===")
        print(f"URL: {current_url}")

        request = requests.get(url=current_url, headers=header)
        time.sleep(0.5)
        bs = BeautifulSoup(request.text, 'lxml')

        # Crawl poems on this page
        poems_on_page, skip_mode = crawl_poems_on_page(bs, header, base_dir_name, page_num, total_poems, last_poem if skip_mode else None, flog)
        total_poems += poems_on_page

        print(f"Found {poems_on_page} poems on page {page_num}")

        # Look for next page link
        next_link = bs.find('a', string=re.compile('下一页'))
        if next_link and next_link.get('href'):
            next_href = next_link.get('href')
            # Handle relative URL
            if not next_href.startswith('http'):
                current_url = "https://www.gushiwen.cn" + next_href
            else:
                current_url = next_href
            page_num += 1
        else:
            # No more pages
            print(f"\nNo more pages found.")
            current_url = None

    return total_poems


def main():
    header = {
        "user-agent": "Mozilla/5.0(Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36(KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36"
    }

    # URL for Su Shi's poems
    url = "https://www.gushiwen.cn/shiwens/default.aspx?astr=%e8%8b%8f%e8%bd%bc"

    # Output directory name
    base_dir_name = 'su-shi-poems'

    # Create log directory
    if not os.path.exists("log"):
        os.makedirs("log")

    # Read log to find last crawled poem (for resume)
    last_poem = read_log()
    if last_poem:
        print(f"[RESUME MODE] Last crawled poem: {last_poem}")
        print(f"Will resume from the next poem...\n")
    else:
        print("[FRESH START] No previous log found, starting from beginning\n")

    # Create output directory
    if not os.path.exists(base_dir_name):
        os.makedirs(base_dir_name)

    # Open log file for appending
    flog = open('log/crawl_poems_log.txt', 'a', buffering=1, encoding="utf-8")

    # Start crawling
    total = crawl_poems_list(url, header, base_dir_name, last_poem, flog)

    # Close log file
    flog.close()

    print(f"\n{'='*50}")
    print(f"Done! Crawled {total} poems total")
    print(f"All poems saved to '{base_dir_name}' directory")
    print(f"Log saved to 'log/crawl_poems_log.txt'")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
