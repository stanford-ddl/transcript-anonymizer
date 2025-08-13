# Transcript Anonymizer

This Streamlit application automatically redacts sensitive information from transcript files using [Microsoft Presidio](https://github.com/microsoft/presidio).  
It is designed for anonymizing transcriptions of Stanford Deliberative Democracy Lab sessions, but can be used for any text-based content.

## Features
- **File formats supported:** `.txt` and `.xlsx`
- **User-configurable settings:**
  - Select which entity types to redact from a predefined list (e.g., `PERSON`, `LOCATION`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `ORGANIZATION`, etc.)
  - Choose your own redaction replacement text (default: `REDACTED`)
- **Customizable column selection** for Excel files
- **Clear, consistent replacement** for all detected entities
- **Download redacted output** in the same format as uploaded

## How It Works
1. Choose which entity types Presidio should detect.
2. Set the replacement text to be used for redacted entities.
3. Upload a `.txt` or `.xlsx` transcript file.
4. For `.xlsx` files, choose which column contains the text to redact.
5. The app detects only your selected entities and replaces them with your chosen text.
6. Download the anonymized file.

## Usage
The tool is deployed online — no installation required.

1. Visit **[ddl-transcript-anonymizer.streamlit.app](https://ddl-transcript-anonymizer.streamlit.app)**
2. Select entity types to redact from the dropdown.
3. Enter your preferred replacement text.
4. Upload your `.txt` or `.xlsx` transcript file.
5. (For Excel files) Select the column containing the text to redact.
6. View the redacted text directly in the browser.
7. Download your anonymized file in the same format as uploaded.

## Customization
- **Entities to redact**: Configured via the dropdown menu; defaults to `PERSON` and `LOCATION`.
- **Replacement text**: Configured via the input field; defaults to `REDACTED`.
- **Exclusion list**: Certain location terms like "United States" are not redacted (can be changed in code).
- **Entity list**: You can expand or reduce `ENTITY_OPTIONS` in the code.

## License
MIT License — You are free to modify and distribute this tool.
