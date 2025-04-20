## Plan to Complete 作業指示書.md

This document outlines the plan to complete the `作業指示書.md` file by implementing the necessary code and content as described in the file.

### Overall Plan

1.  **Review the `作業指示書.md` file:** Re-read the `作業指示書.md` file to understand the requirements for each module and file.
2.  **Create a plan for each module:** Create a detailed plan for each module, outlining the steps required to implement the functionality described in the `作業指示書.md` file.
3.  **Implement the modules:** Switch to code mode and implement the modules according to the plans created in the previous step.
4.  **Write unit tests:** Write unit tests for each module to ensure that it is working correctly.
5.  **Integrate the modules:** Integrate the modules to create a complete system.
6.  **Test the system:** Test the system to ensure that it is working correctly.
7.  **Document the system:** Document the system to make it easy to use and maintain.

### Detailed Plan for Each Module

#### Data Collection

*   **`playwright_scraper.py`:** Implement the `PlaywrightTwitterScraper` class to scrape data from X.com using Playwright.
    1.  Set up Playwright and initialize the browser.
    2.  Implement login functionality to X.com, handling 2-factor authentication if necessary.
    3.  Retrieve search queries from `config/scraping_targets.yaml`.
    4.  Implement tweet searching based on the retrieved search queries, handling infinite scrolling.
    5.  Extract necessary information (ID, text, date, URL, image URL, etc.) from tweet elements using Playwright's locator API and auto-waiting features.
    6.  Save the collected raw data in JSON format under the `data/raw_scraped_data/` directory, naming files with the collection date and query.
    7.  Implement an option to enable Playwright tracing.
    8.  Implement measures to handle rate limits, errors, and account locks.
*   **`list_collector.py`:** Implement the `TwitterListInfoCollector` class to collect information from X.com lists.
    1.  Retrieve X.com list URLs from `config/scraping_targets.yaml`.
    2.  Extract a list of members (profile URLs) from the specified X.com list URL.
    3.  Access each member's profile page and extract profile information (bio, pinned tweet, etc.) using the locator API.
    4.  Save the collected profile information under the `data/raw_scraped_data/` directory.

#### Data Processing

*   **`text_normalizer.py`:** Implement functions to normalize and clean text data.
    1.  Implement functions to remove unnecessary characters (some emojis, special symbols, etc.) from the collected text data (tweet text, profiles, etc.).
    2.  Implement functions to expand shortened URLs.
    3.  Implement functions to unify full-width/half-width characters.
*   **`event_info_extractor.py`:** Implement the `EventInformationExtractor` class to extract event information from text data.
    1.  Implement logic to extract event information from normalized text using regular expressions, keyword matching, etc.
    2.  Target event information: event name, date and time (supporting various notations), organizer name, location (world name, instance type), hashtags.
    3.  Make extraction rules manageable via a configuration file (e.g., `config/main_config.yaml`).
    4.  Map the extraction results to the data structure defined in `models/event_data_model.py`.
*   **`ai_event_enhancer.py`:** Implement the `GeminiEventDataEnhancer` class to enhance event data using the Google Gemini API.
    1.  Safely read the API key from environment variables or a configuration file.
    2.  Implement logic to generate appropriate prompts based on the event data content.
    3.  Implement a batch processing function, considering the cost and efficiency of API calls.

#### Data Integration

*   **`event_deduplicator.py`:** Implement the `EventDuplicateHandler` class to detect and handle duplicate events.
    1.  Implement logic to receive an event list and detect potentially duplicate events, calculating the similarity of titles, dates, organizers, etc.
    2.  Implement rules to integrate (merge) event information determined to be duplicates, considering the freshness and completeness of the information.
    3.  Make duplicate determination thresholds adjustable via a configuration file.
*   **`schema_validator.py`:** Implement a function to validate event data against a JSON schema.
    1.  Implement a function to verify that the processed and integrated event data meets the correct format, type, and constraints based on the JSON schema defined in `models/data_schemas.py`.
    2.  Output details to the log if a validation error occurs.
*   **`recurring_event_handler.py`:** Implement the `RecurringEventHandler` class to identify and handle recurring events.
    1.  Implement logic to identify recurring event patterns (weekly, bi-weekly, monthly, etc.) from information in the event data (title, description, day of the week, etc.).
    2.  Implement a function to generate (expand) future event instances for a specified period (e.g., the next 60 days) based on the identified pattern.
    3.  Assign the `is_regular` flag and `frequency` information to the generated event instances.

#### Data Publishing

*   **`calendar_file_generator.py`:** Implement the `CalendarFileGenerator` class to generate calendar files in CSV and ICS formats.
    1.  Receive a list of validated event data (`data/validated_events/`) as input.
    2.  Generate a Google Calendar-compatible CSV file and output it to `data/published_outputs/google_calendar_export.csv`.
    3.  Generate an iCalendar (.ics) file and output it to `data/published_outputs/events.ics`.
    4.  Implement processing to accurately convert recurring event repeat rules (RRULE) to CSV and ICS formats.
*   **`json_api_generator.py`:** Implement the `JsonApiGenerator` class to generate JSON API data for VRChat and the web UI.
    1.  Implement a function to generate lightweight JSON API data (`public/api/events.json`) for use in VRChat worlds (UdonSharp), narrowing down the fields to the bare minimum.
    2.  Implement a function to generate JSON data containing detailed information (`web_frontend/api_data/events_web.json`, etc.) for use in the web UI.
*   **`web_content_updater.py`:** Implement the `WebContentUpdater` class to generate and update static HTML files for the web UI.
    1.  Implement a function to generate and update static HTML files (weekly lists, calendar displays, etc.) under the `web_frontend/` directory using the generated JSON data and templates.

#### Common

*   **`configuration_manager.py`:** Implement a class to manage configuration settings.
*   **`logger_setup.py`:** Implement a function to set up logging.
*   **`error_handling.py`:** Implement functions to handle errors.
*   **`data_storage_handler.py`:** Implement functions to handle data input and output.

#### Main Executor

*   **`main_executor.py`:** Implement the main execution script to control the data pipeline.
    1.  Implement a function to parse command-line arguments (execution mode: `collect`, `process`, `publish`, `all`, etc.).
    2.  Implement a function to load configuration files (`config/*.yaml`) (using `src/common/configuration_manager.py`).
    3.  Implement a function to set up logging (using `src/common/logger_setup.py`).
    4.  Implement control logic to execute each processing pipeline (`pipelines/*.py`) in the appropriate order according to the specified mode.

#### Pipelines

*   **`data_pipeline.py`:** Implement the data pipeline to orchestrate the data collection, processing, integration, and publishing steps.

#### Web Frontend

*   **`index.html`:** Implement the web UI to display event information.
    1.  Create a static web page that reads JSON API data (`web_frontend/api_data/events_web.json`, etc.) generated by the data distribution 담당 and displays event information.
    2.  Implement a weekly event list display screen.
    3.  Implement an event display screen in a monthly calendar format.
    4.  Implement event search and filtering functions (organizer, tags, time period, etc.) in JavaScript.
    5.  Adjust the CSS to support responsive design and display properly on both PC and mobile devices.

#### VRChat Assets

*   **`calendar_script.cs`:** Implement the UdonSharp calendar script to display event information in VRChat.
    1.  Develop an UdonSharp script that asynchronously retrieves and parses the lightweight JSON API (`public/api/events.json`) generated by the data distribution 담당 within the VRChat world.
    2.  Implement logic to display the acquired event information in UI elements (TextMeshPro, etc.) within the world.
    3.  Implement display switching by date and time period, and event detail display functions.

#### Config

*   **`main_config.yaml`:** Define the main configuration settings.
*   **`scraping_targets.yaml`:** Define the scraping targets for the data collection module.

#### Models

*   **`event_data_model.py`:** Define the data model for event data.
*   **`data_schemas.py`:** Define the JSON schema for event data.