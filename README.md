import requests
import shutil
import os
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus
import concurrent.futures
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox

DEFAULT_URL = "https://google.com"

class WebScraperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SScraper")

        self.url_var = tk.StringVar()
        self.project_name_var = tk.StringVar()

        tk.Label(root, text="Enter URL:").pack(pady=5)
        self.url_entry = ttk.Entry(root, textvariable=self.url_var)
        self.url_entry.pack(pady=5)

        tk.Label(root, text="Select Folder Output:").pack(pady=5)
        self.project_name_var.set(os.getcwd())
        self.project_name_entry = ttk.Entry(root, textvariable=self.project_name_var, state="disabled")
        self.project_name_entry.pack(pady=5)

        self.browse_button = ttk.Button(root, text="Select Folder", command=self.browse_output_directory)
        self.browse_button.pack(pady=5)

        self.start_button = ttk.Button(root, text="Start Extraction", command=self.start_extraction)
        self.start_button.pack(pady=10)

    def browse_output_directory(self):
        selected_directory = filedialog.askdirectory()
        if selected_directory:
            self.project_name_var.set(selected_directory)
            self.project_name_entry.config(state="normal")
        else:
            self.project_name_var.set(os.getcwd())
            self.project_name_entry.config(state="disabled")

    def start_extraction(self):
        url = self.url_var.get() or DEFAULT_URL
        project_name = self.project_name_var.get()

        session = requests.session()

        try:
            print(f"URL: {url}")
            print(f"Project Name: {project_name}")

            extractor = Extractor(url, session, project_name)
            print(f"Extracting files from {url} to {project_name}\n")
            extractor.run()

            messagebox.showinfo("Extraction Complete", "Web scraping and download completed successfully.")
        except Exception as e:
            shutil.rmtree(project_name, ignore_errors=True)
            print(f"Extraction failed. Directory '{project_name}' removed.\nError: {e}")

class Extractor:
    def __init__(self, url, session, project_name):
        self.url = url
        self.session = session
        self.soup = BeautifulSoup(self.get_page_content(url), "html.parser")
        self.output_folder = project_name or urlparse(url).netloc

    def run(self):
        output_directory = os.path.join(os.path.dirname(os.path.realpath(__file__)), self.output_folder)

        # Check if the soup object is None
        if self.soup is None:
            print("Soup object is None. Extraction aborted.")
            return

        shutil.rmtree(output_directory, ignore_errors=True)
        os.makedirs(output_directory)

        scraped_urls = self.extract_and_save_files()
        print(f"\nTotal extracted files: {len(scraped_urls)}")

    def get_page_content(self, url):
        try:
            content = self.session.get(url)
            content.encoding = 'utf-8'
            print(content.text)  # Add this line to print the content
            return content.text
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching {url}: {e}")
            return None

    def extract_and_save_files(self):
        script_urls = self.extract_and_save_scripts()
        assets_urls = self.extract_and_save_assets()

        return script_urls + assets_urls

    def extract_and_save_scripts(self):
        script_urls = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            script_urls = list(executor.map(self.get_script_url, self.soup.find_all("script")))

        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(self.download_and_save_file, script_urls)

        return script_urls

    def get_script_url(self, tag):
        script_url = tag.attrs.get("src")
        if script_url and not script_url.startswith('http'):
            script_url = urljoin(self.url, script_url)
        return script_url

    def download_and_save_file(self, url):
        if url:
            try:
                response = self.session.get(url)
                response.raise_for_status()

                output_path = os.path.join(self.output_folder, self.url_to_local_path(url, keep_query=True))

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

    def extract_and_save_assets(self):
        form_attr = self.scrap_form_attr()
        a_attr = self.scrap_a_attr()
        img_attr = self.scrap_img_attr()
        link_attr = self.scrap_link_attr()
        btn_attr = self.scrap_btn_attr()

        assets_urls = form_attr + a_attr + img_attr + link_attr + btn_attr
        assets_urls = list(dict.fromkeys(assets_urls))

        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(self.download_and_save_file, assets_urls)

        return assets_urls

    def scrap_form_attr(self):
        form_urls = []
        for form_tag in self.soup.find_all("form"):
            action_url = form_tag.attrs.get("action")
            if action_url:
                form_url = urljoin(self.url, action_url)
                form_urls.append(form_url)
        return form_urls

    def scrap_a_attr(self):
        return [tag.attrs.get("href") for tag in self.soup.find_all("a")]

    def scrap_img_attr(self):
        return [tag.attrs.get("src") for tag in self.soup.find_all("img")]

    def scrap_link_attr(self):
        return [tag.attrs.get("href") for tag in self.soup.find_all("link")]

    def scrap_btn_attr(self):
        return [tag.attrs.get("value") for tag in self.soup.find_all("button")]

    def url_to_local_path(self, url, keep_query=False):
        parsed_url = urlparse(url)
        path = parsed_url.path
        if not path:
            path = "/index.html"
        if not keep_query:
            path = parsed_url.path.split('?')[0]
        return os.path.normpath(quote_plus(path))

if __name__ == "__main__":
    logging.basicConfig(filename='web_scraper.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    root = tk.Tk()
    app = WebScraperGUI(root)
    root.mainloop()
