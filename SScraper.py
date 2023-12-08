import asyncio
import requests
import logging
import os
from bs4 import BeautifulSoup
import concurrent.futures
from urllib.parse import urljoin, urlparse, quote_plus
import argparse
from scrapy import Spider, Item, Field
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

DEFAULT_URL = "https://google.com"

class ExtractedItem(Item):
    url = Field()
    content = Field()

class MySpider(Spider):
    name = 'my_spider'

    def __init__(self, *args, **kwargs):
        super(MySpider, self).__init__(*args, **kwargs)
        self.start_urls = [kwargs.get('url')]

    def parse(self, response):
        item = ExtractedItem()
        item['url'] = response.url
        item['content'] = response.text
        yield item

def get_page_content(url, headers):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        print(response.text)  # Print the content
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def extract_and_save_files(url, project_name, content):
    soup = BeautifulSoup(content, "html.parser")

    script_urls = extract_and_save_scripts(url, soup)
    assets_urls = extract_and_save_assets(url, soup)

    return script_urls + assets_urls

def extract_and_save_scripts(url, soup):
    script_urls = []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        script_urls = list(executor.map(get_script_url, soup.find_all("script"), url=url))

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(download_and_save_file, script_urls, project_name=urlparse(url).netloc)

    return script_urls

def get_script_url(tag, url):
    script_url = tag.attrs.get("src")
    if script_url and not script_url.startswith('http'):
        script_url = urljoin(url, script_url)
    return script_url

def download_and_save_file(url, project_name):
    if url:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            output_path = os.path.join(project_name, url_to_local_path(url, keep_query=True))

            if os.path.exists(output_path):
                remote_modified = response.headers.get('Last-Modified')
                local_modified = os.path.getmtime(output_path)

                if remote_modified and (os.path.getmtime(output_path) >= remote_modified):
                    print(f"Skipped download: {os.path.basename(output_path)} already up to date.")
                    return

            with open(output_path, "wb") as file:
                file.write(response.content)

            print(f"Downloaded {os.path.basename(output_path)} to {os.path.relpath(output_path)}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error downloading {url}: {e}")

def extract_and_save_assets(url, soup):
    form_attr = scrap_form_attr(url, soup)
    a_attr = scrap_a_attr(soup)
    img_attr = scrap_img_attr(soup)
    link_attr = scrap_link_attr(soup)
    btn_attr = scrap_btn_attr(soup)

    assets_urls = form_attr + a_attr + img_attr + link_attr + btn_attr
    assets_urls = list(dict.fromkeys(assets_urls))

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(download_and_save_file, assets_urls, project_name=urlparse(url).netloc)

    return assets_urls

def scrap_form_attr(url, soup):
    form_urls = []
    for form_tag in soup.find_all("form"):
        action_url = form_tag.attrs.get("action")
        if action_url:
            form_url = urljoin(url, action_url)
            form_urls.append(form_url)
    return form_urls

def scrap_a_attr(soup):
    return [tag.attrs.get("href") for tag in soup.find_all("a")]

def scrap_img_attr(soup):
    return [tag.attrs.get("src") for tag in soup.find_all("img")]

def scrap_link_attr(soup):
    return [tag.attrs.get("href") for tag in soup.find_all("link")]

def scrap_btn_attr(soup):
    return [tag.attrs.get("value") for tag in soup.find_all("button")]

def url_to_local_path(url, keep_query=False):
    parsed_url = urlparse(url)
    path = parsed_url.path
    if not path:
        path = "/index.html"
    if not keep_query:
        path = parsed_url.path.split('?')[0]
    return os.path.normpath(quote_plus(path))

def main():
    parser = argparse.ArgumentParser(description='Command line web scraper.')
    parser.add_argument('--url', type=str, default=DEFAULT_URL, help='URL to scrape (default: Google)')
    parser.add_argument('--project_name', type=str, default=None, help='Name of the project (default: Netloc of URL)')
    args = parser.parse_args()

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    
    content = get_page_content(args.url, headers)

    if content:
        project_name = args.project_name or urlparse(args.url).netloc
        scraped_urls = extract_and_save_files(args.url, project_name, content)
        print(f"\nTotal extracted files: {len(scraped_urls)}")

if __name__ == "__main__":
    logging.basicConfig(filename='web_scraper.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main()
