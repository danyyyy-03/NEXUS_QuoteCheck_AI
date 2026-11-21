# NEXUS QuoteCheck AI — v0.1.0

**A local-first Windows application for reviewing supplier quotations and comparing materials at identical requested quantities.**

**Status:** Experimental MVP · **Python:** 3.12 · **License:** MIT

NEXUS QuoteCheck AI imports `.xlsx` and text-based `.pdf` quotations, assists with extracting and matching material lines through **local Ollama**, and produces comparison reports in **Excel, CSV or HTML**.

**The AI does not decide who is cheapest.** All amounts and totals are calculated by deterministic Python code using `Decimal`. Users must review and approve source data before offers are ranked.

## Main capabilities

| Capability | MVP behavior |
|---|---|
| Windows desktop UI | Dark, English-language Tkinter application |
| Excel import | Detects a common header-based quotation table (`Item`, `Qty`, `Unit`, `Unit Price`, `Line Total`), including rows further down the sheet |
| PDF import | Extracts selectable text locally with PyMuPDF; simple pipe-separated demo table is parsed without AI |
| Local AI extraction | Uses Ollama `/api/chat` with structured JSON; every AI line remains unapproved |
| Product mapping | Exact-name + same-unit matches; optional AI suggestions require explicit user selection and confirmation |
| Human validation | Edit quantity, unit, unit price, line total and reference mapping; approve individually or in batches |
| Fair comparison | Reference-basket quantities, matching units, common currency, net-price normalization; duplicates and missing lines block ranking |
| Export | HTML audit report, formula-injection-safe CSV, formatted Excel workbook |
| Project save/load | Local `.nqc.json` file with reviewed items, mappings and source references |
| Demo | Two `.xlsx` quotations plus a text-based `.pdf`, all fictional |

## Windows setup

**Requirements:** Windows 10/11, Python **3.12 64-bit**, about 300 MB free for Python dependencies. **Ollama** must be installed and running for AI features. No cloud API subscription is required.

1. Extract the supplied ZIP into a new directory. Open the folder containing `app.py`, `run.bat` and `setup.bat`.
2. Double-click **`setup.bat`** once. This creates `.venv` and installs `openpyxl` and `PyMuPDF` (internet required for installation).
3. Double-click **`run.bat`**.
4. To use Ollama, run `ollama list` in Windows CMD. For example, use an installed `qwen2.5:3b` model, or run `ollama pull qwen2.5:3b` to install it.
5. In the app, choose the model in the toolbar and click **Refresh Models** to test local connectivity.

The UI can start without Ollama; importing standardized Excel files and comparing confirmed lines does not require any AI model.

## Five-minute demo

1. Click **Load Demo**. This imports three fictional offers from `samples/`.
2. Select **Supplier_Alpha** on the left, read its items, then click **Approve All** only after checking the source sample file.
3. Select **Supplier_Beta**, review and approve its four items. Do the same with **Supplier_Gamma** (three items).
4. Click **Auto-Map Exact Names**. This links products with identical names and identical units to the reference list.
5. Open **Compare Offers & Export**. Choose **Supplier_Alpha** as the reference (if not already selected) and click **Compare Verified Quotes**.
6. Expected **net material totals** (RON): Alpha **934.00**, Beta **908.00**. Gamma has **one missing reference product** and is **NOT RANKED** despite its lower subtotal.
7. Try **Export Excel**, **Export CSV**, or **Export HTML** to save a report.

These are completely **fictional** prices and suppliers; they are for testing only.

## Working with real quotations

1. Import two or more supplier `.xlsx` / `.pdf` files.
2. Verify supplier names, currencies and **Price type**. By default the app assumes `RON` and `Net (excl. VAT)`; these defaults **must be confirmed against the originals**.
3. If a PDF or unusual Excel sheet did not yield items, select its offer and press **Extract with Ollama**. The model returns candidate rows. Never treat them as automatically trusted.
4. Manually edit/check rows, including **quantity**, **unit**, **unit price**, **line total** and **evidence**. Approve only genuinely checked items.
5. Choose a **Reference basket** with *all* required materials. When the reference changes, all old mappings are cleared on purpose.
6. Run **Auto-Map Exact Names** for identical descriptions. For different descriptions, double-click an alternate supplier item and choose a reference product in the mapping dropdown. Confirm technical equivalence and the unit of measure.
7. You can also use **AI Suggest Mappings**, but the suggestions are not applied until you select and confirm them.
8. Compare. Incomplete, duplicate, unapproved, unknown-VAT, mixed-currency or unit-mismatch lines are explicitly marked as non-comparable.
9. Save the project locally using **Save Project**. The `.nqc.json` file **contains quotation data**, so keep it private.

## Pricing and comparison policy

- All amounts use `Decimal`, with two-decimal line-total rounding (HALF_UP).
- The reference basket defines the materials **and quantities** to compare. The quoted unit price is multiplied by reference quantity only when the unit of measure matches.
- Unit conversion is **not automatic**. A `box`, `roll`, `piece` or `meter` may differ materially; inspect the source and adjust manually.
- Results are expressed as **net material cost**. For offers marked `Gross (incl. VAT)`, a **confirmed** VAT percentage must be entered to calculate approximate pre-VAT unit prices. VAT rates are not guessed.
- Different currencies are never silently converted. Exchange rates are not inferred.
- Missing items, duplicate mapping, unapproved lines, invalid amount and unknown VAT exclude an offer from ranking.
- Reports label the lowest **complete, verified, comparable offer only among eligible offers**. An incomplete offer might turn out cheaper after clarification; this is not a universal supplier recommendation.
- **Excluded from rankings:** shipping, discounts, minimum order quantities, delivery windows, warranties, availability, technical compatibility beyond user-confirmed mapping, contractual conditions, tax-deductibility and commercial credit risk.

## AI privacy and limitations

- Ollama is called at `http://127.0.0.1:11434` on the user's machine. No quotation text is intentionally uploaded to an external cloud by the application.
- AI can hallucinate or omit lines. For each extracted row, the app retains a source note and may flag evidence strings not found verbatim.
- The first 45,000 extracted characters from a document are available for AI extraction, divided into up to seven chunks. Very long documents can be truncated. Always compare against the originals.
- PDF files containing scans or images need OCR, which is **not part of this MVP**. The app does not attempt to infer text from pictures.
- Spreadsheet formulas are read as cached values (`data_only=True`); formulas without cached values can be missing and require correction.
- The source file is never modified by importing. Saved projects and reports are local.
- Never upload real client quotations, saved project files, or secrets to a public repository.

## Testing

```bat
py -3.12 -m unittest discover -s tests -v
```

Or double-click `test.bat` after setup. Unit tests mock Ollama's response, and the GUI tests run only where a display is available. The user should verify with their own local Ollama instance.

## Experimental executable

Double-click `build.bat` after setup to install PyInstaller and attempt a Windows `.exe` build. If successful, find `dist\NEXUS_QuoteCheck_AI.exe`. The demo sample files are bundled into the executable. **Building and testing a Windows EXE must happen on Windows.** The ZIP supplied here is Python source, not a precompiled executable. Ollama remains a separate local installation.

## Project structure

```text
NEXUS_QuoteCheck_AI_v0.1.0/
├─ app.py
├─ nexus_quotecheck/
│  ├─ models.py           Decimal pricing and validation
│  ├─ sources.py          Excel and PDF import
│  ├─ ollama_client.py    Local Ollama extraction/suggestions
│  ├─ matching.py         Human-confirmed item mapping
│  ├─ compare.py          Deterministic audited comparison
│  ├─ report.py           Excel, CSV, HTML report output
│  └─ ui.py               Windows GUI
├─ samples/               Two synthetic Excel quotes and one PDF
├─ tests/                 Model, parser, audit, UI and export tests
├─ setup.bat
├─ run.bat
├─ test.bat
├─ build.bat
├─ requirements.txt
├─ START_HERE_RO.md
├─ LICENSE
└─ .gitignore
```

## License

MIT — see `LICENSE`.

**Optional developer helper:** `make_samples.py` regenerates the fictional sample PDF and requires `reportlab`, which is not required to run the application. The included sample PDF is ready to use.

*Experimental decision-support software. Not a substitute for professional procurement review.*
