import asyncio
import json
import os
from datetime import datetime

from playwright.async_api import async_playwright


class PlaywrightTwitterScraper:
    def __init__(self, config_manager, logger=None):
        self.config_manager = config_manager
        self.logger = logger
        self.scraping_targets = self.config_manager.get('scraping_targets')
        self.raw_data_dir = 'data/raw_scraped_data/'
        if not os.path.exists(self.raw_data_dir):
            os.makedirs(self.raw_data_dir)

    async def initialize_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch()
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()

    async def close_browser(self):
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()

    async def login_to_twitter(self):
        print("Login functionality not implemented yet.")
        pass

    async def scrape_tweets(self, query):
        try:
            await self.page.goto(f"https://twitter.com/search?q={query}&src=typed_query")
            previous_height = 0
            while True:
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.page.wait_for_selector("article:last-child", timeout=3000)
                current_height = await self.page.evaluate("document.body.scrollHeight")
                if current_height == previous_height:
                    break
                previous_height = current_height

            tweets = []
            tweet_elements = await self.page.locator("article").all()
            for tweet_element in tweet_elements:
                try:
                    # Extract tweet URL
                    tweet_url_element = tweet_element.locator("a[href*='/status/']").first()
                    tweet_url = "https://twitter.com" + await tweet_url_element.get_attribute("href")

                    # Extract tweet ID from URL
                    tweet_id = tweet_url.split("/")[-1]

                    # Extract tweet text
                    try:
                        tweet_text = await tweet_element.locator("div[lang]").inner_text()
                    except:
                        tweet_text = ""

                    # Extract tweet date
                    time_element = tweet_element.locator("time").first()
                    tweet_date = await time_element.get_attribute("datetime")

                    tweets.append({
                        "tweet_id": tweet_id,
                        "text": tweet_text,
                        "url": tweet_url,
                        "date": tweet_date
                    })
                except Exception as e:
                    print(f"Error extracting tweet info: {e}")

            return tweets

        except Exception as e:
            self.logger.error(f"Error during scraping: {e}")
            return []

    async def save_data(self, data, query):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize the query string to remove invalid characters from filename
        safe_query = "".join(x for x in query if x.isalnum())
        filename = f"{self.raw_data_dir}tweets_{safe_query}_{timestamp}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            file_size = os.path.getsize(filename)
            if file_size < 100:
                self.logger.warning(f"Raw data file {filename} is too small: {file_size} bytes")
                return False
            self.logger.info(f"Data saved to {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving data to {filename}: {e}")
            return False

    async def scrape(self):
        await self.initialize_browser()
        # await self.login_to_twitter()

        all_tweets = []
        for target in self.scraping_targets:
            query = target.get('query')
            if query:
                tweets = await self.scrape_tweets(query)
                if tweets:
                    if await self.save_data(tweets, query):
                        all_tweets.extend(tweets)
            else:
                self.logger.warning(f"No query specified for target: {target}")

        await self.close_browser()
        return all_tweets

    async def main(self):
        results = await self.scrape()
        return results

if __name__ == "__main__":
    class ConfigManager:
        def get(self, key):
            if key == 'scraping_targets':
                return [{'query': '#VRChat event'}]
            return None

    config_manager = ConfigManager()
    scraper = PlaywrightTwitterScraper(config_manager)
    asyncio.run(scraper.main())