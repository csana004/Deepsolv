# ---------------------- Imports ----------------------
from fastapi import FastAPI, Query, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import random
import json

from database import SessionLocal, engine, Base
from models_db import Brand
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

# ---------------------- App Init ----------------------
app = FastAPI()
Base.metadata.create_all(bind=engine)

# ---------------------- Retry + Rotate Headers ----------------------
def fetch_url(url, retries=3):
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36"
    ]
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(1.5, 4))
            headers = {"User-Agent": random.choice(user_agents)}
            res = requests.get(url, timeout=10, headers=headers, allow_redirects=True)
            if res.status_code == 429:
                continue
            elif res.status_code in [200, 301, 302]:
                return res
        except requests.RequestException:
            continue
    return None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------- Models ----------------------
class Product(BaseModel):
    title: str
    url: Optional[str]
    image: Optional[str]
    price: Optional[str]

class BrandInsights(BaseModel):
    store_name: Optional[str]
    website_url: str
    hero_products: List[Product]
    product_catalog: List[Product]
    privacy_policy: Optional[str]
    return_policy: Optional[str]
    refund_policy: Optional[str]
    faqs: Optional[List[str]]
    social_handles: Optional[List[str]]
    contact_details: Optional[List[str]]
    about_brand: Optional[str]
    important_links: Optional[List[str]]

# ---------------------- Helper Functions ----------------------
def clean_text(text):
    return ' '.join(text.strip().split())

def extract_faqs(soup):
    faqs = set()
    for tag in soup.find_all(['p', 'li', 'div', 'span']):
        text = clean_text(tag.get_text())
        if text.endswith('?') and 10 < len(text) < 200:
            answer_tag = tag.find_next_sibling()
            answer = clean_text(answer_tag.get_text()) if answer_tag else ""
            faqs.add(f"{text}\n{answer}")
    return list(faqs)[:10]

def extract_contacts(soup):
    text = soup.get_text()
    emails = re.findall(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', text)
    phones = re.findall(r'\+?\d[\d\s\-]{8,}\d', text)
    return list(set(emails + phones))

def extract_social_links(soup):
    links = [a['href'] for a in soup.find_all('a', href=True)]
    return [l for l in links if any(x in l for x in ['instagram.com', 'facebook.com', 'twitter.com', 'tiktok.com'])]

def extract_policy_text(store_url, keywords):
    homepage_res = fetch_url(store_url)
    if not homepage_res:
        return None

    soup = BeautifulSoup(homepage_res.content, 'html.parser')
    links = []
    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        text = link.get_text(strip=True).lower()
        if any(k in href or k in text for k in keywords):
            links.append(urljoin(store_url, link["href"]))

    links = list(set(links))
    if not links:
        return None

    links.sort(key=lambda x: sum(k in x for k in keywords))

    for link in links:
        policy_res = fetch_url(link)
        if policy_res:
            policy_soup = BeautifulSoup(policy_res.content, "html.parser")
            main = policy_soup.find("main") or policy_soup.find("article") or policy_soup.body
            if main:
                text = clean_text(main.get_text())[:2000]
                if len(text) > 100:
                    return text
    return None

def get_price_from_product_page(product_url):
    res = fetch_url(product_url)
    if res:
        soup = BeautifulSoup(res.content, 'html.parser')
        for cls in ['.price-item--sale', '.price-item--regular', '.price', '.product-price']:
            tag = soup.select_one(cls)
            if tag:
                price = clean_text(tag.get_text())
                return re.sub(r'(?i)\bfrom\b\s*', '', price).strip()
    return None

def extract_hero_products(soup, base_url):
    hero_products = []
    seen_titles = set()
    for a in soup.select('a[href*="/products/"]'):
        href = a.get('href')
        if not href:
            continue
        full_url = urljoin(base_url, href)
        title = clean_text(a.get_text()) or a.get('title', '')
        if not title or title in seen_titles or len(title) > 100:
            continue

        parent = a.find_parent(['div', 'li', 'article']) or a
        price = None
        for cls in ['.price-item--sale', '.price-item--regular', '.price', '.product-price']:
            price_tag = parent.select_one(cls)
            if price_tag:
                price = clean_text(price_tag.get_text())
                break
        if not price:
            price = get_price_from_product_page(full_url)
        if price:
            price = re.sub(r'(?i)\bfrom\b\s*', '', price).strip()

        img_tag = parent.find('img')
        image_url = img_tag['src'] if img_tag and img_tag.get('src') else None
        if image_url and image_url.startswith('//'):
            image_url = 'https:' + image_url

        hero_products.append(Product(
            title=title,
            url=full_url,
            image=image_url,
            price=price
        ))

        seen_titles.add(title)

    return hero_products

# ---------------------- Scraping Logic ----------------------
def scrape_shopify_site(url: str) -> BrandInsights:
    if not url.startswith("http"):
        url = "https://" + url

    response = fetch_url(url)
    if not response:
        raise HTTPException(status_code=401, detail="Website could not be fetched or does not exist.")

    soup = BeautifulSoup(response.content, 'html.parser')
    title = soup.title.string.strip() if soup.title else ""
    og_site = soup.find("meta", property="og:site_name")
    store_name = og_site["content"].strip() if og_site else title

    hero_products = extract_hero_products(soup, url)

    product_catalog = []
    catalog_url = urljoin(url, '/products.json')
    products_resp = fetch_url(catalog_url)
    if products_resp:
        try:
            products_json = products_resp.json()
            for product in products_json.get('products', []):
                product_catalog.append(Product(
                    title=product.get('title'),
                    url=urljoin(url, f"/products/{product.get('handle')}"),
                    image=product['images'][0]['src'] if product['images'] else None,
                    price=str(product.get('variants', [{}])[0].get('price', ''))
                ))
        except:
            pass

    privacy_policy = extract_policy_text(url, ['privacy'])
    return_policy = extract_policy_text(url, ['return', 'exchange', 'ecoreturns'])
    refund_policy = extract_policy_text(url, ['refund'])

    faqs = extract_faqs(soup)
    contact_details = extract_contacts(soup)
    social_handles = extract_social_links(soup)

    about_section = soup.find(lambda tag: tag.name in ['section', 'div'] and tag.get('id') and 'about' in tag['id'].lower())
    about_brand = clean_text(about_section.get_text()) if about_section else None

    links = [a['href'] for a in soup.find_all('a', href=True)]
    important_links = [l for l in links if any(x in l.lower() for x in ['contact', 'track', 'blog', 'faq'])]

    if not about_brand:
        for tag in soup.find_all(['section', 'div']):
            if 'about' in tag.get_text(strip=True).lower():
                about_brand = clean_text(tag.get_text())
                if len(about_brand) > 50:
                    break

    if not contact_details:
        for link in links:
            if 'contact' in link.lower():
                contact_url = urljoin(url, link)
                contact_res = fetch_url(contact_url)
                if contact_res:
                    contact_soup = BeautifulSoup(contact_res.content, 'html.parser')
                    contact_details = extract_contacts(contact_soup)
                break

    if not refund_policy:
        refund_policy = return_policy

    catalog_map = {p.url: p for p in product_catalog}
    for hp in hero_products:
        match = catalog_map.get(hp.url)
        if match:
            if not hp.image:
                hp.image = match.image
            if not hp.price:
                hp.price = match.price

    return BrandInsights(
        store_name=store_name,
        website_url=url,
        hero_products=hero_products,
        product_catalog=product_catalog,
        privacy_policy=privacy_policy,
        return_policy=return_policy,
        refund_policy=refund_policy,
        faqs=faqs,
        social_handles=social_handles,
        contact_details=contact_details,
        about_brand=about_brand,
        important_links=list(set(important_links))
    )

# ---------------------- FastAPI Routes ----------------------
@app.get("/scrape", response_model=BrandInsights)
def scrape(url: str, db: Session = Depends(get_db)):
    data = scrape_shopify_site(url)
    existing = db.query(Brand).filter(Brand.website_url == data.website_url).first()
    if not existing:
        brand = Brand(
            website_url=data.website_url,
            store_name=data.store_name,
            about=data.about_brand,
            contact=json.dumps(data.contact_details),
            faqs=json.dumps(data.faqs),
            shipping_policy=data.privacy_policy,
            return_policy=data.return_policy,
            refund_policy=data.refund_policy
        )
        db.add(brand)
        db.commit()
    return data

@app.get("/brands")
def get_all_brands(db: Session = Depends(get_db)):
    brands = db.query(Brand).all()
    results = [
        {
            "website_url": b.website_url,
            "store_name": b.store_name,
            "about": b.about,
            "contact": json.loads(b.contact),
            "faqs": json.loads(b.faqs),
            "shipping_policy": b.shipping_policy,
            "return_policy": b.return_policy,
            "refund_policy": b.refund_policy
        }
        for b in brands
    ]
    return JSONResponse(content=results)
