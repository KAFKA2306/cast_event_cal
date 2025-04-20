import argparse
import asyncio
from src.common.configuration_manager import ConfigurationManager
from src.common.logger_setup import setup_logger
from src.data_collection.playwright_scraper import PlaywrightTwitterScraper

def main():
    parser = argparse.ArgumentParser(description="VRChat Event Calendar Data Pipeline")
    parser.add_argument("--all", action="store_true", help="Run all pipelines")
    parser.add_argument("--collect", action="store_true", help="Run data collection pipeline")
    parser.add_argument("--process", action="store_true", help="Run data processing pipeline")
    parser.add_argument("--publish", action="store_true", help="Run data publishing pipeline")
    args = parser.parse_args()

    config_manager = ConfigurationManager("config/main_config.yaml", "config/scraping_targets.yaml", "models/data_schemas.py")
    logger = setup_logger("main_executor", config_manager.get("log_file", "app.log"))

    logger.info(f"Starting data pipeline")

    from pipelines.data_pipeline import DataPipeline
    pipeline = DataPipeline(logger=logger)

    async def run_pipeline():
        if args.all or args.collect or args.process or args.publish:
            await pipeline.run("all")
        elif args.collect:
            await pipeline.run("collect")
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