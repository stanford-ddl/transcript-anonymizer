import streamlit as st
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
Upload a transcription file in .txt format, and it will automatically redact sensitive information.""")
uploaded_file = st.file_uploader("Upload a .txt file", type="txt")

if uploaded_file is not None:
    text = uploaded_file.read().decode("utf-8")

    # Only names & locations; start with a modest threshold
    target_entities = ["PERSON", "GPE", "LOC"]
    raw_results = analyzer.analyze(
        text=text,
        language="en",
        entities=target_entities,
        score_threshold=0.6
    )

    # Post-filter to reduce false positives:
    # - PERSON must be higher confidence
    # - GPE/LOC slightly looser (to catch rarer place names)
    # - drop lowercase single words (e.g., "yourself", "facilitate")
    results = []
    results = []
    for r in raw_results:
        if r.entity_type == "PERSON" and r.score < 0.85:
            continue
        if r.entity_type in {"GPE", "LOC"} and r.score < 0.70:
            continue
        results.append(r)

    # Redact with clear labels
    redacted = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators={
            "DEFAULT": OperatorConfig("replace", {"new_value": "**REDACTED**"}),
            "PERSON": OperatorConfig("replace", {"new_value": "[NAME]"}),
            "GPE": OperatorConfig("replace", {"new_value": "[LOCATION]"}),
            "LOC": OperatorConfig("replace", {"new_value": "[LOCATION]"}),
        }
    ).text

    st.subheader("Redacted text:")
    st.text_area("", redacted, height=300)

    st.download_button(
        label="Download redacted file",
        data=redacted.encode("utf-8"),
        file_name="redacted.txt",
        mime="text/plain"
    )
