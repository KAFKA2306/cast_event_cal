from src.data_collection.playwright_scraper import EnhancedTwitterScraper
from src.data_processing.event_info_extractor import EventInformationExtractor
from src.data_integration.event_deduplicator import EventDuplicateHandler
from src.data_publishing.calendar_file_generator import CalendarFileGenerator
from src.common.configuration_manager import ConfigurationManager
from src.common.logger_setup import setup_logger

import asyncio
from src.data_collection.list_collector import TwitterListInfoCollector
from src.data_processing.event_info_extractor import EventInformationExtractor
from src.data_integration.event_deduplicator import EventDuplicateHandler
from src.data_integration.schema_validator import validate_schema
from src.data_integration.recurring_event_handler import RecurringEventHandler
from src.data_publishing.calendar_file_generator import CalendarFileGenerator
from src.data_publishing.json_api_generator import JsonApiGenerator
from src.data_publishing.web_content_updater import WebContentUpdater
from src.common.configuration_manager import ConfigurationManager
from src.common.logger_setup import setup_logger
from src.common.data_storage_handler import save_data, load_data
import os

class DataPipeline:
    def __init__(self, config_file="config/main_config.yaml", logger=None):
        self.config_manager = ConfigurationManager(config_file)
        self.logger = logger or setup_logger("data_pipeline", self.config_manager.get_config().get("log_file", "app.log"))
        self.config = self.config_manager.config
        self.scraper = EnhancedTwitterScraper(self.config_manager)
        self.list_collector = TwitterListInfoCollector(self.config_manager)
        self.extractor = EventInformationExtractor(self.config_manager)
        self.deduplicator = EventDuplicateHandler(self.config_manager)
        self.schema_validator = validate_schema
        self.recurring_event_handler = RecurringEventHandler(self.config_manager)
        self.calendar_generator = CalendarFileGenerator(self.config_manager)
        self.json_api_generator = JsonApiGenerator(self.config_manager)
        self.web_content_updater = WebContentUpdater(self.config_manager)
        self.raw_data_dir = 'data/raw_scraped_data/'
        self.validated_events_dir = 'data/validated_events/'
        self.integrated_events_dir = 'data/integrated_events/'
        self.published_outputs_dir = 'data/published_outputs/'
        # Ensure the directories exist
        if not os.path.exists(self.validated_events_dir):
            os.makedirs(self.validated_events_dir)
        if not os.path.exists(self.integrated_events_dir):
            os.makedirs(self.integrated_events_dir)
        if not os.path.exists(self.published_outputs_dir):
            os.makedirs(self.published_outputs_dir)
        if not os.path.exists("data/integrated_events"):
            os.makedirs("data/integrated_events")

    async def run(self, mode):
        self.logger.info(f"Running data pipeline in {mode} mode")

        if mode == "collect" or mode == "all":
            self.logger.info("Collecting data...")
            scrape_tasks = []
            for target in self.config_manager.get_config().get('scraping_targets'):
                if 'query' in target:
                    query = target['query']
                    scrape_tasks.append(self.scraper.scrape_tweets(query=query))
            all_tweets_results = await asyncio.gather(*scrape_tasks)
            all_tweets = {}
            for result in all_tweets_results:
                all_tweets.update(result)
            all_tweets_list = []
            if all_tweets:
                for tweet_data in all_tweets.values():
                    all_tweets_list.extend(tweet_data)

            all_list_members = await self.list_collector.collect()
            all_list_members_list = []
            if all_list_members:
                for list_data in all_list_members.values():
                    all_list_members_list.extend(list_data)

            all_raw_data = all_tweets_list + all_list_members_list
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            raw_data_filename = f"{self.raw_data_dir}all_raw_data_{timestamp}.json"
            save_data(all_raw_data, raw_data_filename)
            self.logger.info(f"Raw data saved to {raw_data_filename}")
            if os.path.getsize(raw_data_filename) == 0:
                self.logger.warning("Raw data file is empty. Skipping data processing.")
                return

        if mode == "process" or mode == "all":
            self.logger.info("Processing data...")
            raw_data_filename = f"{self.raw_data_dir}all_raw_data_*.json"
            raw_data_files = glob.glob(raw_data_filename)
            if not raw_data_files:
                self.logger.warning("No raw data files found. Skipping data processing.")
                return

            all_events = []
            for raw_data_file in raw_data_files:
                raw_data = load_data(raw_data_file)
                if not raw_data:
                    self.logger.warning(f"Raw data file {raw_data_file} is empty. Skipping processing.")
                    continue
                for item in raw_data:
                    event_info = self.extractor.extract(item['text'])
                    all_events.append(event_info)

            validated_events = []
            data_schemas = self.config_manager.get_config().get('data_schemas')
            for event in all_events:
                if self.schema_validator(event, data_schemas):
                    validated_events.append(event)
                else:
                    self.logger.warning(f"Event failed schema validation: {event}")

            timestamp = now.strftime("%Y%m%d_%H%M%S")
            validated_events_filename = f"{self.validated_events_dir}validated_events_{timestamp}.json"
            save_data(validated_events, validated_events_filename)
            self.logger.info(f"Validated events saved to {validated_events_filename}")

        if mode == "integrate" or mode == "all":
            self.logger.info("Integrating data...")
            validated_events_filename = f"{self.validated_events_dir}validated_events_*.json"
            validated_events_files = glob.glob(validated_events_filename)
            if not validated_events_files:
                self.logger.warning("No validated events files found. Skipping data integration.")
                return

            all_validated_events = []
            for validated_events_file in validated_events_files:
                validated_events = load_data(validated_events_file)
                all_validated_events.extend(validated_events)

            deduplicated_events = self.deduplicator.deduplicate(all_validated_events)
            recurring_events = self.recurring_event_handler.handle_recurring_events(deduplicated_events)

            timestamp = now.strftime("%Y%m%d_%H%M%S")
            integrated_events_filename = f"data/integrated_events/integrated_events_{timestamp}.json"
            save_data(recurring_events, integrated_events_filename)
            self.logger.info(f"Integrated events saved to {integrated_events_filename}")

        if mode == "publish" or mode == "all":
            self.logger.info("Publishing data...")
            integrated_events_files = glob.glob(f"{self.integrated_events_dir}integrated_events_*.json")
            if not integrated_events_files:
                self.logger.warning("No integrated events files found. Skipping data publishing.")
                return

            all_integrated_events = []
            for integrated_events_file in integrated_events_files:
                integrated_events = load_data(integrated_events_file)
                all_integrated_events.extend(integrated_events)

            self.calendar_generator.generate_calendar_files(all_integrated_events)
            self.json_api_generator.generate_json_api(all_integrated_events)
            self.web_content_updater.update_web_content(all_integrated_events)

            self.logger.info("Data publishing completed.")

        self.logger.info("Data pipeline completed")

import asyncio
import glob
from datetime import datetime
now = datetime.now()

async def main():
    pipeline = DataPipeline()
    await pipeline.run("all")

if __name__ == "__main__":
    asyncio.run(main())