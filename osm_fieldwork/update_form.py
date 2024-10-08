from io import BytesIO

import pandas as pd
from python_calamine.pandas import pandas_monkeypatch

from osm_fieldwork.xlsforms import xlsforms_path

# Monkeypatch pandas to add calamine driver
pandas_monkeypatch()


def merge_sheets(mandatory_df, custom_df, digitisation_df):
    # Remove rows with None in 'name' column
    if "name" in mandatory_df.columns:
        mandatory_df = mandatory_df.dropna(subset=["name"])
    if "name" in custom_df.columns:
        custom_df = custom_df.dropna(subset=["name"])
    if "name" in digitisation_df.columns:
        digitisation_df = digitisation_df.dropna(subset=["name"])

    # Identify common fields between custom_df and mandatory_df or digitisation_df
    common_fields = (
        set(custom_df["name"])
        .intersection(set(mandatory_df["name"]))
        .union(set(custom_df["name"]).intersection(set(digitisation_df["name"])))
    )

    # Keep common fields from custom_df in their original order
    custom_common_df = custom_df[custom_df["name"].isin(common_fields)]
    custom_non_common_df = custom_df[~custom_df["name"].isin(common_fields)]

    # Filter out the common fields from the mandatory_df and digitisation_df
    mandatory_df_filtered = mandatory_df[~mandatory_df["name"].isin(common_fields)]
    digitisation_df_filtered = digitisation_df[~digitisation_df["name"].isin(common_fields)]

    group_row = pd.DataFrame(
        {
            "type": ["begin group"],
            "name": ["survey_questions"],
            "label": ["Survey Form"],
            "relevant": [
                "${building_exists} = 'yes'"
            ],  # Add the relevant condition to display this group only if "Yes" is selected
        }
    )

    end_group_row = pd.DataFrame({"type": ["end group"], "name": ["end_survey_questions"], "label": ["End Survey Form"]})

    # Concatenate: mandatory fields at the top, custom common fields, remaining custom fields, and finally append form fields
    merged_df = pd.concat(
        [custom_common_df, mandatory_df_filtered, group_row, custom_non_common_df, digitisation_df_filtered, end_group_row],
        ignore_index=True,
    )

    return merged_df


def update_xls_form(custom_form: BytesIO) -> BytesIO:
    custom_sheets = pd.read_excel(custom_form, sheet_name=None, engine="calamine")
    default_form_path = f"{xlsforms_path}/fmtm/mandatory_fields.xls"
    digitisation_form_path = f"{xlsforms_path}/fmtm/digitisation_fields.xls"
    digitisation_sheets = pd.read_excel(digitisation_form_path, sheet_name=None, engine="calamine")
    mandatory_sheets = pd.read_excel(default_form_path, sheet_name=None, engine="calamine")

    # Process and merge the 'survey' sheet if present in all forms
    if "survey" in mandatory_sheets and "survey" in digitisation_sheets and "survey" in custom_sheets:
        custom_sheets["survey"] = merge_sheets(mandatory_sheets["survey"], custom_sheets["survey"], digitisation_sheets["survey"])

    # Process and merge the 'choices' sheet if present in all forms
    if "choices" in mandatory_sheets and "choices" in digitisation_sheets and "choices" in custom_sheets:
        custom_sheets["choices"] = merge_sheets(
            mandatory_sheets["choices"], custom_sheets["choices"], digitisation_sheets["choices"]
        )

    # Append or overwrite the existing entities sheet
    if "entities" in mandatory_sheets:
        custom_sheets["entities"] = mandatory_sheets["entities"]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in custom_sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    output.seek(0)
    return output
