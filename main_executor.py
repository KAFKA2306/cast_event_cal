import os
import argparse
import asyncio
from src.common.configuration_manager import ConfigurationManager
from src.common.logger_setup import setup_logger
from src.data_collection.playwright_scraper import EnhancedTwitterScraper

def main():
    parser = argparse.ArgumentParser(description="VRChat Event Calendar Data Pipeline")
    parser.add_argument("--all", action="store_true", help="Run all pipelines")
    parser.add_argument("--collect", action="store_true", help="Run data collection pipeline")
    parser.add_argument("--process", action="store_true", help="Run data processing pipeline")
    parser.add_argument("--publish", action="store_true", help="Run data publishing pipeline")
    args = parser.parse_args()

    config_manager = ConfigurationManager("config/main_config.yaml")
    logger = setup_logger("main_executor", log_level="INFO", log_filename=config_manager.get_config().get("log_file", "app.log"))

    logger.info(f"Starting data pipeline")

    from pipelines.data_pipeline import DataPipeline
    pipeline = DataPipeline(logger=logger)

    async def run_pipeline():
        if args.collect:
            logger.info("Starting loop to collect data until no new data is found...")
            previous_files = set()
            while True:
                current_files = set(os.listdir('data/raw_scraped_data'))
                new_files = current_files - previous_files
                if not new_files and previous_files: # No new files and not the first run
                    logger.info("No new data files found in this iteration. Exiting loop.")
                    break
                previous_files = current_files
                logger.info("Running data collection pipeline...")
                await pipeline.run("collect")
                logger.info("Data collection pipeline iteration completed.")
                await asyncio.sleep(5)  # Wait for 5 seconds before next iteration
        elif args.all or args.process or args.publish:
            await pipeline.run("all")
        elif args.process:
            await pipeline.run("process")
        elif args.publish:
            await pipeline.run("publish")
        else:
            logger.info("No mode specified. Exiting.")

    asyncio.run(run_pipeline())

    logger.info("Data pipeline completed")

if __name__ == "__main__":
    main()