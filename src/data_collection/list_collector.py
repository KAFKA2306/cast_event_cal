import asyncio
import json
import os
from datetime import datetime

from playwright.async_api import async_playwright


class TwitterListInfoCollector:
    def __init__(self, config_manager, logger=None):
        self.config_manager = config_manager
        self.logger = logger
        self.scraping_targets = self.config_manager.get('scraping_targets')
        self.raw_data_dir = 'data/raw_scraped_data/'  # Define data directory

        # Ensure the raw data directory exists
        if not os.path.exists(self.raw_data_dir):
            os.makedirs(self.raw_data_dir)

    async def initialize_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch()  # Or use other browsers
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()

    async def close_browser(self):
        await self.context.close()
        await self.browser.close()
        await self.playwright.stop()

    async def collect_list_members(self, list_url):
        try:
            await self.page.goto(list_url)

            # Extract member profile URLs from the list page
            member_urls = []
            member_elements = await self.page.locator("a[href*='/user/']").all()  # Adjust locator as needed
            for member_element in member_elements:
                try:
                    member_url = "https://twitter.com" + await member_element.get_attribute("href")
                    member_urls.append(member_url)
                except Exception as e:
                    print(f"Error extracting member URL: {e}")

            return member_urls

        except Exception as e:
            print(f"Error during list member collection: {e}")
            return []

    async def scrape_profile_info(self, profile_url):
        try:
            await self.page.goto(profile_url)

            # Extract profile information (bio, pinned tweet, etc.)
            try:
                bio_element = self.page.locator("div[data-testid='UserDescription']").first()
                bio = await bio_element.inner_text()
            except Exception as e:
                bio = ""
                print(f"Error extracting bio: {e}")

            # TODO: Extract pinned tweet

            profile_info = {
                "profile_url": profile_url,
                "bio": bio,
                # "pinned_tweet": pinned_tweet
            }

            return profile_info

        except Exception as e:
            print(f"Error during profile scraping: {e}")
            return None
    
        async def save_data(self, data, list_url):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.raw_data_dir}list_members_{list_url.split('/')[-1]}_{timestamp}.json"
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

    async def collect(self):
        await self.initialize_browser()

        all_members_data = []
        for target in self.scraping_targets:
            list_url = target.get('list_url')
            if list_url:
                member_urls = await self.collect_list_members(list_url)
                for member_url in member_urls:
                    profile_info = await self.scrape_profile_info(member_url)
                    if profile_info:
                        all_members_data.append(profile_info)
                if all_members_data and await self.save_data(all_members_data, list_url):
                    pass

        await self.close_browser()
        return all_members_data

    async def main(self):
        results = await self.collect()
        return results

if __name__ == "__main__":
    # Example usage (replace with actual config loading)
    class ConfigManager:
        def get(self, key):
            if key == 'scraping_targets':
                return [{'list_url': 'https://twitter.com/i/lists/1680272194977630208'}]
            return None

    config_manager = ConfigManager()
    collector = TwitterListInfoCollector(config_manager)
    asyncio.run(collector.main())