import streamlit as st
import pandas as pd
import io
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_analyzer.nlp_engine import NlpEngineProvider

# --- Presidio NLP setup ---
nlp_configuration = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}]  # or en_core_web_sm
}
provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
nlp_engine = provider.create_engine()

analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
anonymizer = AnonymizerEngine()

# --- Streamlit UI ---
st.title("Transcript Anonymizer")
st.markdown("""
This tool helps redact sensitive information from transcriptions of Stanford DDL sessions.
It uses Presidio to identify and anonymize names and locations.
Upload a transcription file in `.txt` or `.xlsx` format, and it will automatically redact sensitive information.
""")

uploaded_file = st.file_uploader("Upload a .txt or .xlsx file", type=["txt", "xlsx"])

text = None
file_type = None
df = None
column_choice = None

# --- Read file content ---
if uploaded_file is not None:
    if uploaded_file.name.endswith(".txt"):
        file_type = "txt"
        text = uploaded_file.read().decode("utf-8")

    elif uploaded_file.name.endswith(".xlsx"):
        file_type = "xlsx"
        df = pd.read_excel(uploaded_file)
        column_choice = st.selectbox("Select the column to redact:", df.columns)
        if column_choice:
            # Combine rows into one text block for analysis
            text = "\n".join(df[column_choice].dropna().astype(str))

# --- Process redaction ---
if text:
    # Only detect names (PERSON) and locations (LOCATION)
    target_entities = ["PERSON", "LOCATION"]
    raw_results = analyzer.analyze(
        text=text,
        language="en",
        entities=target_entities,
        score_threshold=0.85
    )

    # Exclude certain location terms from redaction
    EXCLUDE_WORDS = {
        "america", "united states", "us", "usa", "u.s.",
        "the united states", "the us", "the usa", "the u. s."
    }

    results = []
    for r in raw_results:
        entity_text = text[r.start:r.end].lower()
        if entity_text in EXCLUDE_WORDS:
            continue
        results.append(r)

    # Redact with clear labels
    redacted = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators={
            "DEFAULT": OperatorConfig("replace", {"new_value": "**REDACTED**"}),
        }
    ).text

    st.success("Redaction complete!")

    st.subheader("Redacted text:")
    st.text_area("", redacted, height=300)

    # --- Download in the same format as uploaded ---
    if file_type == "txt":
        st.download_button(
            label="Download redacted file",
            data=redacted.encode("utf-8"),
            file_name="redacted.txt",
            mime="text/plain"
        )

    elif file_type == "xlsx" and df is not None and column_choice:
        # Create a copy of the DataFrame to avoid modifying original
        df_redacted = df.copy()
        redacted_rows = redacted.split("\n")
        # Assign redacted values back to same structure
        df_redacted[column_choice + "_REDACTED"] = redacted_rows
        # Save to BytesIO
        output = io.BytesIO()
        df_redacted.to_excel(output, index=False)
        output.seek(0)
        st.download_button(
            label="Download redacted Excel file",
            data=output,
            file_name="redacted.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
