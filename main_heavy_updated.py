import os
import random
import csv
import dateparser
from datetime import datetime
from seleniumbase import SB

def get_random_user_agent():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    return random.choice(user_agents)

def scrape_ticker_with_cycling(ticker_slug, from_date_str, max_pages=1000, batch_size=50):
    from_date = dateparser.parse(from_date_str)
    if not from_date:
        print(f"!!! Error: Could not parse START_DATE '{from_date_str}'")
        return

    os.makedirs("data", exist_ok=True)
    
    # # Check for existing data
    # existing_files = [f for f in os.listdir("data") if f.startswith(f"{ticker_slug}_")]
    # if existing_files:
    #     print(f"[-] SKIPPING: {ticker_slug} (Found existing file: {existing_files[0]})")
    #     return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"data/{ticker_slug}_{timestamp}.csv"
    
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "link", "source", "time", "type"])
        writer.writeheader()

    print(f"[*] INITIALIZING: {ticker_slug} | Target Date: {from_date.date()} | Max Pages: {max_pages}")

    current_page = 1
    total_articles_saved = 0
    keep_crawling = True

    while current_page <= max_pages and keep_crawling:
        batch_end = min(current_page + batch_size - 1, max_pages)
        print(f"\n[Session] Opening fresh browser for {ticker_slug}: Pages {current_page} to {batch_end}")
        
        try:
            with SB(uc=True, incognito=True, headless2=True, xvfb=True, 
                    agent=get_random_user_agent(), page_load_strategy="eager") as sb:
                
                sb.set_window_size(random.randint(1024, 1920), random.randint(768, 1080))
                
                for p in range(current_page, batch_end + 1):
                    url = f"https://www.investing.com/equities/{ticker_slug}-news"
                    if p > 1: url += f"/{p}"
                    
                    print(f"  > Loading P.{p}/{max_pages}: {url}", end="\r")
                    sb.uc_open_with_reconnect(url, 8)
                    
                    try:
                        sb.wait_for_element('article[data-test="article-item"]', timeout=20)
                        sb.execute_script("window.stop();")
                    except Exception:
                        print(f"\n  [!] Timeout/Missing content on P.{p}. Retrying session...")
                        break

                    # Popup & Lazy Load
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
                                print(f"\n[#] Cutoff reached: Article date ({article_dt.date()}) is older than {from_date.date()}.")
                                keep_crawling = False
                                break

                            title_el = art.find_element('css selector', '[data-test="article-title-link"]')

                            source = "N/A"
                            try:
                                source_el = art.find_element('css selector', '[data-test="article-provider-link"]')
                                source = source_el.text.strip()
                            except: pass

                            page_articles.append({
                                "title": title_el.text.strip(),
                                "link": title_el.get_attribute("href"),
                                "source": source,
                                "time": raw_time,
                                "type": "Pro" if "/news/pro/" in title_el.get_attribute("href") else "Free"
                            })
                        except: continue

                    if page_articles:
                        with open(filename, "a", newline="", encoding="utf-8") as f:
                            writer = csv.DictWriter(f, fieldnames=["title", "link", "source", "time", "type"])
                            writer.writerows(page_articles)
                        total_articles_saved += len(page_articles)
                        print(f"  [+] P.{p} Saved: {len(page_articles)} articles (Total: {total_articles_saved})", end="\n")

                    if not keep_crawling: break
                    
                    # Adaptive Sleep
                    if p % 10 == 0:
                        print(f"  [zZz] Batch break: Cooling down...")
                        sb.sleep(random.uniform(20, 30))
                    else:
                        sb.sleep(random.uniform(3, 6))

            current_page = batch_end + 1
            
        except Exception as e:
            print(f"\n[!!!] CRASH in session: {str(e)[:100]}... Refreshing browser.")
            # Small delay to let system clear the crashed process
            import time
            time.sleep(5) 

    print(f"\n[FINISH] {ticker_slug} complete. Total articles archived: {total_articles_saved}\n")

if __name__ == "__main__":
    TICKER_FILE = "tickers.txt"
    # Process only 1 new ticker per workflow run to stay well under 6hrs
    MAX_TO_PROCESS = 1 
    processed_this_run = 0

    if os.path.exists(TICKER_FILE):
        with open(TICKER_FILE, "r") as f:
            tickers = [line.strip() for line in f if line.strip()]
        
        print(f"[*] Queue total: {len(tickers)} tickers.\n{tickers}")
        
        for t in tickers:
            if processed_this_run >= MAX_TO_PROCESS:
                break
            
            # FAST CHECK: Does data for this ticker exist?
            os.makedirs("data", exist_ok=True)
            already_scraped = any(f.startswith(f"{t}_") for f in os.listdir("data"))
            
            if already_scraped:
                print(f"[-] {t}: Already exists in /data. Checking next...")
                continue
            
            # If we reach here, it's a new ticker
            print(f"\n[!] Target Found: {t}. Starting scrape...")
            scrape_ticker_with_cycling(t, "2025-04-01")
            processed_this_run += 1
            
        if processed_this_run == 0:
            print("[✓] All tickers in list have been processed. Nothing to do!")
    else:
        print(f"!!! Error: {TICKER_FILE} not found.")