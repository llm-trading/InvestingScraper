import random
import csv
import os
import dateparser
from seleniumbase import SB

def get_random_user_agent():
    """Returns a random modern User-Agent to rotate digital fingerprints."""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    return random.choice(user_agents)

def scrape_investing_chronological(ticker_slug, from_date_str, max_pages=1000):
    from_date = dateparser.parse(from_date_str)
    if not from_date:
        print(f"Error: Could not parse date '{from_date_str}'.")
        return

    filename = f"{ticker_slug}_news_output.csv"
    
    # CHECKPOINT: Create file with headers if it doesn't exist
    if not os.path.exists(filename):
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["title", "link", "source", "time", "type"])
            writer.writeheader()

    print(f"Workflow Start: Scraping {ticker_slug} up to {max_pages} pages.")

    with SB(uc=True, 
            incognito=True, 
            headless2=True, 
            xvfb=True, 
            agent=get_random_user_agent(), 
            page_load_strategy="eager") as sb:
        
        # RANDOMIZATION: Jitter the window size to vary hardware fingerprint
        sb.set_window_size(random.randint(1024, 1920), random.randint(768, 1080))
        
        sb.driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
            "headers": {"Accept-Language": "en-US,en;q=0.9"}
        })

        keep_crawling = True
        
        for p in range(1, max_pages + 1):
            if not keep_crawling:
                break

            url = f"https://www.investing.com/equities/{ticker_slug}-news"
            if p > 1: url += f"/{p}"
            
            print(f"Loading Page {p}/{max_pages}...")
            sb.uc_open_with_reconnect(url, 8)
            
            try:
                sb.wait_for_element('article[data-test="article-item"]', timeout=20)
                sb.execute_script("window.stop();") 
            except:
                print(f"Page {p}: Content timeout. Retrying once...")
                sb.sleep(5)
                sb.uc_open_with_reconnect(url, 10)
                if not sb.is_element_visible('article[data-test="article-item"]'):
                    break

            # Popup handling
            close_btn = 'svg[data-test="sign-up-dialog-close-button"]'
            if sb.is_element_visible(close_btn):
                sb.uc_click(close_btn)

            sb.execute_script("window.scrollBy(0, 400);")
            sb.sleep(1.5)

            articles = sb.find_elements('article[data-test="article-item"]')
            page_articles = []
            
            for art in articles:
                try:
                    time_el = art.find_element('css selector', '[data-test="article-publish-date"]')
                    raw_time = time_el.get_attribute("datetime") or time_el.text.strip()
                    article_dt = dateparser.parse(raw_time)

                    if article_dt and article_dt < from_date:
                        print(f"Cutoff reached at page {p} ({article_dt}).")
                        keep_crawling = False
                        break 

                    title_el = art.find_element('css selector', '[data-test="article-title-link"]')
                    link = title_el.get_attribute("href")
                    
                    source = "N/A"
                    try:
                        source_el = art.find_element('css selector', '[data-test="article-provider-link"]')
                        source = source_el.text.strip()
                    except: pass

                    page_articles.append({
                        "title": title_el.text.strip(),
                        "link": link,
                        "source": source,
                        "time": raw_time,
                        "type": "Pro" if "/news/pro/" in link else "Free"
                    })
                except Exception:
                    continue

            # CHECKPOINT: Append page data to CSV immediately
            if page_articles:
                with open(filename, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["title", "link", "source", "time", "type"])
                    writer.writerows(page_articles)
                print(f"Page {p} saved ({len(page_articles)} articles).")

            # ADAPTIVE SLEEP: Pulse the scraping to mimic human behavior
            if keep_crawling and p < max_pages:
                if p % 10 == 0:
                    print("Batch break: Resting for 30 seconds...")
                    sb.sleep(random.uniform(25, 35))
                else:
                    sb.sleep(random.uniform(4, 8))

    print(f"Job Complete. All data saved to {filename}.")

if __name__ == "__main__":
    TICKER = "nvidia-corp"
    START_DATE = "2025-04-01" 
    scrape_investing_chronological(TICKER, START_DATE, max_pages=1000)