import streamlit as st
import pandas as pd
import io
import json  # NEW: for JSON export
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_analyzer.nlp_engine import NlpEngineProvider

# --- Presidio NLP setup ---
nlp_configuration = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]  # use _sm on Streamlit for speed
}
provider = NlpEngineProvider(nlp_configuration=nlp_configuration)
nlp_engine = provider.create_engine()

analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
anonymizer = AnonymizerEngine()

# --- Streamlit UI ---
st.title("Transcript Anonymizer")
st.markdown("""
Redacts selected entities from text or Excel files using Microsoft Presidio.
Upload a `.txt` or `.xlsx` file, choose the column (for Excel), pick which entities to redact, and set the replacement text.
""")

# User controls for redaction behavior
redaction_text = st.text_input("Replacement text for redactions", value="**REDACTED**")

# Common Presidio entity types (extend if you like)
ENTITY_OPTIONS = [
    "PERSON", "LOCATION", "EMAIL_ADDRESS", "PHONE_NUMBER", "DATE_TIME",
    "IP_ADDRESS", "URL", "CREDIT_CARD", "US_SSN", "IBAN_CODE", "SWIFT_CODE",
    "ORGANIZATION"
]
selected_entities = st.multiselect(
    "Choose entity types to redact",
    options=ENTITY_OPTIONS,
    default=["PERSON", "LOCATION"],
    help="Only these entities will be detected and redacted."
)

uploaded_file = st.file_uploader("Upload a .txt or .xlsx file", type=["txt", "xlsx"])

text = None
file_type = None
df = None
column_choice = None
orig_index_nonnull = None  # to re-align redactions back into the Excel rows

# --- Read file content ---
if uploaded_file is not None:
    if uploaded_file.name.endswith(".txt"):
        file_type = "txt"
        text = uploaded_file.read().decode("utf-8")

    elif uploaded_file.name.endswith(".xlsx"):
        file_type = "xlsx"
        df = pd.read_excel(uploaded_file)

        # Default to "text" column if present, otherwise first column
        default_index = 0
        if "text" in df.columns:
            default_index = list(df.columns).index("text")

        column_choice = st.selectbox("Select the column to redact:", df.columns, index=default_index)

        if column_choice:
            # Keep track of which rows are non-null so we can put redactions back in-place
            mask = df[column_choice].notna()
            orig_index_nonnull = df.index[mask]
            # Combine only non-null rows for analysis (preserves row count when we split later)
            text = "\n".join(df.loc[orig_index_nonnull, column_choice].astype(str))

# --- Process redaction ---
if text and selected_entities:
    # Analyze only the selected entities
    raw_results = analyzer.analyze(
        text=text,
        language="en",
        entities=selected_entities,
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

    # --- Exportable analysis results (JSON/CSV) ---
    export_data = [r.to_dict() for r in results]
    df_results = pd.DataFrame(export_data)

    # Redact with user-selected replacement
    redacted = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators={
            "DEFAULT": OperatorConfig("replace", {"new_value": redaction_text})
        }
    ).text

    st.success("Redaction complete!")

    st.subheader("Redacted preview:")
    st.text_area("", redacted, height=300)

    # --- Show analysis table preview + downloads ---
    st.subheader("Detected entities (export)")
    if len(df_results) == 0:
        st.info("No entities detected with the current settings.")
    else:
        st.dataframe(df_results, use_container_width=True)
        csv_bytes = df_results.to_csv(index=False).encode("utf-8")
        json_bytes = json.dumps(export_data, indent=2).encode("utf-8")

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="⬇️ Download analysis CSV",
                data=csv_bytes,
                file_name="analysis_results.csv",
                mime="text/csv"
            )
        with col2:
            st.download_button(
                label="⬇️ Download analysis JSON",
                data=json_bytes,
                file_name="analysis_results.json",
                mime="application/json"
            )

    # --- Download in the same format as uploaded ---
    if file_type == "txt":
        st.download_button(
            label="⬇️ Download redacted .txt",
            data=redacted.encode("utf-8"),
            file_name="redacted.txt",
            mime="text/plain"
        )

    elif file_type == "xlsx" and df is not None and column_choice:
        # Create a copy of the DataFrame to avoid modifying original
        df_redacted = df.copy()

        # Split redacted text back to per-row values for the originally non-null rows
        redacted_rows = redacted.split("\n")
        if len(redacted_rows) != len(orig_index_nonnull):
            st.warning("Row alignment mismatch after redaction; check for unexpected newlines in the source data.")

        # Initialize new column and assign redacted values only to rows that had text
        new_col = f"{column_choice}_REDACTED"
        df_redacted[new_col] = ""
        df_redacted.loc[orig_index_nonnull, new_col] = redacted_rows[:len(orig_index_nonnull)]

        # Save to BytesIO for download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_redacted.to_excel(writer, index=False)
        output.seek(0)

        st.download_button(
            label="⬇️ Download redacted .xlsx",
            data=output,
            file_name="redacted.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # --- NEW: Label Studio export (predictions) — ONE TASK PER ROW FOR EXCEL ---
    def _presidio_to_ls_results(text_segment: str):
        """Run analyzer on a segment and return LS-style prediction results."""
        seg_raw = analyzer.analyze(
            text=text_segment,
            language="en",
            entities=selected_entities,
            score_threshold=0.85
        )
        seg_filtered = []
        for rr in seg_raw:
            seg_text = text_segment[rr.start:rr.end].lower()
            if seg_text in EXCLUDE_WORDS:
                continue
            seg_filtered.append(rr)

        ls_results_local = []
        for rr in seg_filtered:
            try:
                snippet = text_segment[rr.start:rr.end]
            except Exception:
                snippet = ""
            ls_results_local.append({
                "from_name": "pii",     # must match <Labels name="pii"> in LS config
                "to_name": "text",      # must match <Text name="text">
                "type": "labels",
                "value": {
                    "start": int(rr.start),
                    "end": int(rr.end),
                    "text": snippet,
                    "labels": [str(rr.entity_type)]
                },
                "score": float(getattr(rr, "score", 0)) if getattr(rr, "score", None) is not None else None
            })
        return ls_results_local

    ls_tasks = []

    if file_type == "xlsx" and df is not None and column_choice:
        # One LS task per non-null row in the chosen column
        nonnull_series = df.loc[orig_index_nonnull, column_choice].astype(str)
        for ridx, row_text in nonnull_series.items():
            if not row_text or not str(row_text).strip():
                continue
            ls_results_row = _presidio_to_ls_results(row_text)
            ls_tasks.append({
                "data": {
                    "text": row_text,
                    "source_file": getattr(uploaded_file, "name", "uploaded.xlsx"),
                    "sheet_column": column_choice,
                    "row_index": int(ridx)
                },
                "predictions": [{
                    "model_version": "presidio-v1",
                    "result": ls_results_row
                }]
            })
    else:
        # TXT (or fallback): single task with the full text
        ls_results_full = _presidio_to_ls_results(text)
        ls_tasks.append({
            "data": {"text": text},
            "predictions": [{
                "model_version": "presidio-v1",
                "result": ls_results_full
            }]
        })

    ls_json_bytes = json.dumps(ls_tasks, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button(
        label="⬇️ Download Label Studio JSON (predictions)",
        data=ls_json_bytes,
        file_name="labelstudio_presidio_predictions.json",
        mime="application/json",
        help="Import into Label Studio (Project → Import). For Excel, this creates one task per row."
    )

elif text and not selected_entities:
    st.info("Select at least one entity type to redact.")
