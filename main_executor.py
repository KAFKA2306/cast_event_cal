# main_executor.py
import argparse
import logging
import yaml
import sys

from src.common.configuration_manager import ConfigurationManager
from src.common.logger_setup import setup_logging
# Import pipeline modules here
# from src.pipelines.daily_collection_pipeline import DailyCollectionPipeline
# from src.pipelines.event_processing_pipeline import EventProcessingPipeline
# from src.pipelines.data_publishing_pipeline import DataPublishingPipeline


def parse_command_line_arguments():
    """
    Parses command line arguments for the main execution script.
    """
    parser = argparse.ArgumentParser(description="Runs the VRChat event calendar pipeline.")
    parser.add_argument(
        "--mode",
        choices=["collect", "process", "publish", "all"],
        default="all",
        help="Execution mode: collect, process, publish, or all.",
    )
    parser.add_argument(
        "--config",
        default="config/main_config.yaml",
        help="Path to the main configuration file.",
    )
    return parser.parse_args()


def main_execution_flow():
    """
    Main execution logic for the VRChat event calendar pipeline.
    """
    args = parse_command_line_arguments()

    # Initialize configuration manager
    config_manager = ConfigurationManager(args.config)
    config = config_manager.get_config()

    # Initialize logging
    logger = setup_logging(config["logging"])
    logger.info("Starting main execution flow.")

    try:
        # Execute pipelines based on the specified mode
        if args.mode == "all" or args.mode == "collect":
            logger.info("Running data collection pipeline.")
            # DailyCollectionPipeline(config["collection"], logger).run()
            logger.info("Data collection pipeline completed.")

        if args.mode == "all" or args.mode == "process":
            logger.info("Running event processing pipeline.")
            # EventProcessingPipeline(config["processing"], logger).run()
            logger.info("Event processing pipeline completed.")

        if args.mode == "all" or args.mode == "publish":
            logger.info("Running data publishing pipeline.")
            # DataPublishingPipeline(config["publishing"], logger).run()
            logger.info("Data publishing pipeline completed.")

        logger.info("Main execution flow completed successfully.")
        return 0  # Success

    except Exception as e:
        logger.error(f"An error occurred during execution: {e}", exc_info=True)
        return 1  # Failure


if __name__ == "__main__":
    sys.exit(main_execution_flow())