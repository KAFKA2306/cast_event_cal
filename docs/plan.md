# Plan to update src directory

This plan outlines the steps to update all files in the `src` directory with the content of `docs\scrape_all_codes.md`.

1.  **Read the content of `docs\scrape_all_codes.md`:**
    *   Use the `read_file` tool to read the content of the file.
2.  **List all files in the `src` directory:**
    *   Use the `list_files` tool with the `recursive` parameter set to `true` to get a list of all files in the `src` directory.
3.  **Iterate through the files in `src` and update their content:**
    *   For each file in the list obtained in step 2, use the `write_to_file` tool to replace the content of the file with the content obtained in step 1.