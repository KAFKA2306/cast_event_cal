# VRChat Event Calendar Aggregator

## Description

This project aggregates VRChat events from various online sources and provides a comprehensive calendar for end-users. 

**Target Audience:** VRChat end-users, community organizers

**Key Features:**

*   Comprehensive VRChat event aggregation
*   Calendar file generation (e.g., iCalendar)
*   JSON API for accessing event data
*   Web content updates with event information

## Prerequisites

*   Python 3.9 or higher
*   pip package installer
*   Python libraries listed in `requirements.txt`
*   Configuration files in the `config/` directory

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url> 
    cd vrc_cast_event_calender
    ```
2.  **Install Python 3.9+:** 
    Follow the instructions for your operating system to install Python 3.9 or a later version.
3.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Linux/macOS
    venv\Scripts\activate  # On Windows
    ```
4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Configure the project:**
    *   Modify the configuration files in the `config/` directory, particularly `config/main_config.yaml` and `config/scraping_targets.yaml`, to adjust settings and scraping targets as needed.

## Usage

To run the project and start the data pipeline, execute the `main_executor.py` script from the project root:

```bash
python main_executor.py
```

## Configuration

The project's configuration is managed through YAML files located in the `config/` directory:

*   `config/main_config.yaml`: Contains the main configuration settings for the project.
*   `config/scraping_targets.yaml`: Defines the targets for event scraping.

Refer to the comments within these files for detailed information on each configuration option.

## Contributing

Contributions are welcome! To contribute to this project, please submit pull requests on GitHub. 

## License

This project is licensed under the MIT License.