import random
import csv
import dateparser
from seleniumbase import SB

def get_random_user_agent():
    """Returns a random modern User-Agent to avoid 'Datacenter' detection."""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    return random.choice(user_agents)

def scrape_investing_chronological(ticker_slug, from_date_str, max_pages=15):
    from_date = dateparser.parse(from_date_str)
    if not from_date:
        print(f"Error: Could not parse date '{from_date_str}'.")
        return []

    print(f"Workflow Start: Scraping {ticker_slug} from {from_date_str}")

    # GitHub/Linux Optimized Configuration
    with SB(uc=True, 
            incognito=True, 
            headless2=True, 
            xvfb=True,        # Required for GitHub Actions
            agent=get_random_user_agent(), # User-Agent Jitter
            page_load_strategy="eager") as sb:
        
        # Additional Linux performance flags
        sb.driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
            "headers": {"Accept-Language": "en-US,en;q=0.9"}
        })

        final_valid_articles = []
        keep_crawling = True
        
        for p in range(1, max_pages + 1):
            if not keep_crawling:
                break

            url = f"https://www.investing.com/equities/{ticker_slug}-news"
            if p > 1: url += f"/{p}"
            
            print(f"Loading Page {p}...")
            # Longer reconnect for GitHub's network stack
            sb.uc_open_with_reconnect(url, 7)
            
            try:
                # Wait for core content
                sb.wait_for_element('article[data-test="article-item"]', timeout=15)
                sb.execute_script("window.stop();") 
            except:
                print(f"Page {p}: Content timeout. Stopping.")
                break

            # Handle Popups
            close_btn = 'svg[data-test="sign-up-dialog-close-button"]'
            if sb.is_element_visible(close_btn):
                sb.sleep(1)
                sb.uc_click(close_btn)

            # Scroll to trigger any lazy-loaded source tags
            sb.execute_script("window.scrollBy(0, 400);")
            sb.sleep(1.5)

            articles = sb.find_elements('article[data-test="article-item"]')
            
            for art in articles:
                try:
                    time_el = art.find_element('css selector', '[data-test="article-publish-date"]')
                    raw_time = time_el.get_attribute("datetime") or time_el.text.strip()
                    article_dt = dateparser.parse(raw_time)

                    # CHRONOLOGICAL BREAK
                    if article_dt and article_dt < from_date:
                        print(f"Cutoff reached: {article_dt}.")
                        keep_crawling = False
                        break 

                    title_el = art.find_element('css selector', '[data-test="article-title-link"]')
                    link = title_el.get_attribute("href")
                    
                    source = "N/A"
                    try:
                        source_el = art.find_element('css selector', '[data-test="article-provider-link"]')
                        source = source_el.text.strip()
                    except: pass

                    final_valid_articles.append({
                        "title": title_el.text.strip(),
                        "link": link,
                        "source": source,
                        "time": raw_time,
                        "type": "Pro" if "/news/pro/" in link else "Free"
                    })
                except Exception:
                    continue

            print(f"Page {p} complete. Current Count: {len(final_valid_articles)}")
            
            if keep_crawling and p < max_pages:
                sb.sleep(random.uniform(4, 7)) # Increased sleep for GitHub safety

        return final_valid_articles

if __name__ == "__main__":
    TICKER = "nvidia-corp"
    # Set this to a few days back for the first run
    START_DATE = "2026-03-04" 
    
    results = scrape_investing_chronological(TICKER, START_DATE)
    
    if results:
        filename = f"{TICKER}_news_output.csv"
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["title", "link", "source", "time", "type"])
            writer.writeheader()
            writer.writerows(results)
        print(f"Job finished. Saved {len(results)} articles.")