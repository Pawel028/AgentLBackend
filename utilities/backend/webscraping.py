import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import json
import csv

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' 
                  '(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
}

# Custom exceptions
class ScrapingError(Exception):
    pass

def fetch_html(url, timeout=10):
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        raise ScrapingError(f"Request failed for {url}: {e}")

def clean_text(text):
    return ' '.join(text.strip().split())

def parse_html(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        "url": base_url,
        "title": soup.title.string.strip() if soup.title else "",
        "meta_description": "",
        "headings": [],
        "paragraphs": [],
        "links": []
    }

    # Meta Description
    meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    if meta and meta.get('content'):
        data['meta_description'] = clean_text(meta['content'])

    # Headings
    for tag in ['h1', 'h2', 'h3']:
        for element in soup.find_all(tag):
            text = clean_text(element.get_text())
            if text:
                data['headings'].append((tag, text))

    # Paragraphs
    for p in soup.find_all('p'):
        text = clean_text(p.get_text())
        if text:
            data['paragraphs'].append(text)

    # Links
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = clean_text(a.get_text())
        full_url = urljoin(base_url, href)
        if urlparse(full_url).scheme in ['http', 'https']:
            data['links'].append({'text': text, 'url': full_url})

    return data

def scrape_website(url):
    print(f"🔍 Scraping: {url}")
    html = fetch_html(url)
    return parse_html(html, url)

def scrape_multiple_sites(url_list, delay_between=2):
    all_data = []
    for url in url_list:
        try:
            data = scrape_website(url)
            all_data.append(data)
        except ScrapingError as e:
            print(f"❌ Skipping {url}: {e}")
        time.sleep(delay_between)  # Optional: be nice to servers
    return all_data

def save_to_json(data, filename='scraped_data.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_to_csv(data, filename='scraped_data.csv'):
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['URL', 'Title', 'Meta Description', 'Headings', 'Paragraph Count', 'Link Count'])
        for d in data:
            writer.writerow([
                d['url'],
                d['title'],
                d['meta_description'],
                '; '.join([f"{tag}: {text}" for tag, text in d['headings']]),
                len(d['paragraphs']),
                len(d['links'])
            ])

if __name__ == '__main__':
    urls_to_scrape = [
        'https://en.wikipedia.org/wiki/Web_scraping',
        'https://www.bbc.com/news/technology',
        'https://www.python.org/',
        'https://www.nytimes.com/',
    ]

    scraped_results = scrape_multiple_sites(urls_to_scrape)
    
    save_to_json(scraped_results, 'results.json')
    save_to_csv(scraped_results, 'results.csv')
    
    print("✅ Scraping complete! Data saved to 'results.json' and 'results.csv'")
