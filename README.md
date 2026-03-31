# Client Import & Reconciliation Tool

A Streamlit web app that converts client timesheet files to the standard import format and reconciles them against system exports using fuzzy name matching.

## Features

- **Template-based conversion** -- Select a client format template and upload the file. Supports multiple layouts (punch-based, weekly grid).
- **Name matching** -- Fuzzy name matching via [name-matcher](https://github.com/brianohanlon703/name-matcher) handles name variations (e.g. reversed order, missing punctuation, nicknames).
- **Reconciliation** -- Compares client hours against system export by name + date, flags mismatches and missing entries.
- **Download** -- Export converted import file or reconciliation report as CSV/Excel.

## Supported Templates

| Template | Layout | Description |
|---|---|---|
| Staffing Agency Horizontal | One row per punch (clock in/out) | Employee name, In/Out times, hours |
| Client Weekly Grid | One row per employee per week, day columns | Daily hours across Mon-Sun columns |

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deployment

Hosted on [Streamlit Community Cloud](https://streamlit.io/cloud) (free).
