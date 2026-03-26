
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import boto3
import re
import time

# =========================
# 🔹 S3 CONFIG
# =========================
s3 = boto3.client('s3')
BUCKET = "gov-schemes-raw"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# =========================
# 🔹 COMMON UTILS
# =========================
def clean_filename(name):
    name = re.sub(r'[^\w\s-]', '', name)
    return name.strip().replace(" ", "_")[:80]


def upload_text(content, key):
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=content.encode("utf-8")
    )
    print(f"✅ Uploaded TXT: {key}")


def upload_pdf(url, key):
    try:
        response = requests.get(url, headers=HEADERS, stream=True, timeout=60)
        if response.status_code == 200:
            s3.upload_fileobj(response.raw, BUCKET, key)
            print(f"✅ Uploaded PDF: {key}")
        else:
            print(f"❌ PDF failed: {url}")
    except Exception as e:
        print(f"❌ PDF error: {e}")


# =========================
# 🔥 1. NSP SCRAPER (PDF)
# =========================
def scrape_nsp():
    print("\n🚀 Starting NSP scraping...")

    BASE_URL = "https://scholarships.gov.in"
    URL = "https://scholarships.gov.in/All-Scholarships"

    response = requests.get(URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")

    seen = set()
    count = 0

    for link in soup.find_all("a", href=True):

        href = link["href"]
        full_url = urljoin(BASE_URL, href)
        url_lower = full_url.lower()

        if (
            "/public/schemeguidelines/" in url_lower
            and url_lower.endswith(".pdf")
            and "faq" not in url_lower
            and "not_available" not in url_lower
            and "_f.pdf" not in url_lower
        ):

            if full_url not in seen:

                filename = full_url.split("/")[-1]
                key = f"nsp/pdfs/{filename}"

                upload_pdf(full_url, key)

                seen.add(full_url)
                count += 1

                time.sleep(0.5)

    print(f"🎯 NSP Done: {count} PDFs uploaded")


# =========================
# 🔥 2. PROJECT SARTHI
# =========================
def scrape_projectsarthi():
    print("\n🚀 Starting ProjectSarthi scraping...")

    BASE_URL = "https://projectsarthi.com/scholarships/"

    response = requests.get(BASE_URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")

    links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if "/scholarships/" in href and href != BASE_URL:
            full_link = urljoin(BASE_URL, href)

            if "page" not in full_link:
                links.add(full_link)

    print("Found:", len(links))

    for link in links:
        try:
            page = requests.get(link, headers=HEADERS)
            page_soup = BeautifulSoup(page.text, "html.parser")

            article = page_soup.find("article")
            text = article.get_text("\n", strip=True) if article else page_soup.get_text("\n", strip=True)

            title_tag = page_soup.find("h1")
            title = title_tag.text.strip() if title_tag else "scholarship"

            filename = clean_filename(title) + ".txt"
            key = f"projectsarthi/txt/{filename}"

            upload_text(text, key)

            time.sleep(0.5)

        except Exception as e:
            print("❌ Error:", e)


# =========================
# 🔥 3. INDIA SCHOLARSHIPS
# =========================
def scrape_india_scholarships():
    print("\n🚀 Starting IndiaScholarships scraping...")

    base_url = "https://www.indiascholarships.in"
    url = "https://www.indiascholarships.in/scholarships-in/all-india"

    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")

    scholarship_links = []

    for link in soup.find_all("a", href=True):

        href = link["href"]
        title = link.text.strip()

        if "/scholarships/" in href and len(title) > 10:

            if href.startswith("/"):
                href = base_url + href

            scholarship_links.append({
                "title": title,
                "link": href
            })

    unique_links = {v["link"]: v for v in scholarship_links}.values()

    print("Found:", len(unique_links))

    for item in unique_links:
        try:
            title = item["title"]
            link = item["link"]

            page = requests.get(link, headers=HEADERS)
            soup = BeautifulSoup(page.text, "html.parser")

            paragraphs = soup.find_all("p")
            description = " ".join([p.text.strip() for p in paragraphs])

            lists = soup.find_all("li")
            details = [li.text.strip() for li in lists]

            content = f"TITLE: {title}\n\nLINK: {link}\n\nDESCRIPTION:\n{description}\n\nDETAILS:\n"
            for d in details:
                content += f"- {d}\n"

            filename = clean_filename(title) + ".txt"
            key = f"indiascholarships/txt/{filename}"

            upload_text(content, key)

            time.sleep(0.5)

        except Exception as e:
            print("❌ Error:", e)


# =========================
# 🚀 MAIN EXECUTION
# =========================
def main():
    scrape_nsp()
    scrape_projectsarthi()
    scrape_india_scholarships()

    print("\n🎉 ALL SCRAPING COMPLETED & UPLOADED TO S3")


if __name__ == "__main__":
    main()
