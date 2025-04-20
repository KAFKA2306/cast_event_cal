# Architecture

## Overview

This project is designed to collect event data from various online sources, integrate and validate the data, enhance it with AI, and publish it to different platforms.

## Components

1.  **Data Collection:**
    *   **Playwright Scraper:** Uses Playwright to scrape data from websites.
    *   **List Collector:** Collects data from lists.

2.  **Data Integration:**
    *   **Event Deduplicator:** Deduplicates events from different sources.
    *   **Recurring Event Handler:** Handles recurring events.
    *   **Schema Validator:** Validates data against a predefined schema.

3.  **Data Processing:**
    *   **AI Event Enhancer:** Enhances event information using AI.
    *   **Event Info Extractor:** Extracts event information from text.
    *   **Text Normalizer:** Normalizes text data.

4.  **Data Publishing:**
    *   **Calendar File Generator:** Generates calendar files (e.g., iCalendar).
    *   **JSON API Generator:** Generates a JSON API for accessing the data.
    *   **Web Content Updater:** Updates web content with the data.

## Data Flow

1.  Data is collected from online sources using the Data Collection components.
2.  The collected data is integrated and validated using the Data Integration components.
3.  The integrated data is processed and enhanced using the Data Processing components.
4.  The processed data is published to different platforms using the Data Publishing components.

## Configuration

The project uses a configuration file (`config/main_config.yaml`) to manage settings and parameters. Scraping targets are defined in `config/scraping_targets.yaml`.

## Data Storage

Raw scraped data is stored in the `data/raw_scraped_data/` directory. Integrated and validated events are stored in the `data/validated_events/` directory. Published outputs are stored in the `data/published_outputs/` directory.

## Models

Data schemas are defined in `models/data_schemas.py`. The event data model is defined in `models/event_data_model.py`.

## Common

The `src/common/` directory contains common modules used throughout the project, such as:

*   `web_structure_analyzer.py`: Analyzes the structure of web pages.
*   `adaptive_selectors.py`: Provides adaptive selectors for web scraping.
*   `configuration_manager.py`: Manages configuration settings.
*   `data_storage_handler.py`: Handles data storage operations.
*   `error_handling.py`: Handles errors.
*   `logger_setup.py`: Sets up logging.