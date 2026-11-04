# Regional market pages implementation plan

**Goal:** Give the United States, mainland China, Europe and Hong Kong dedicated dashboard pages while retaining the global dataset explorer and all existing US views.

**Architecture:** Reuse the existing reviewed global observations and dictionary. Add regional presentation components and pure scope/date helpers; keep collectors, native frequencies, dataset formats, SDK and the Monday 08:00 Hong Kong cloud schedule unchanged. Europe initially covers Germany, France and the United Kingdom as separate national markets, not an invented regional aggregate.

**Scope:** The user requested market pages in the existing published dashboard. Existing international macro coverage is annual World Bank GDP growth, CPI inflation and ILO modeled unemployment. Named equity closes are daily; OECD share-price indices remain monthly. All Markdown remains English. Publish to the existing authorized public GitHub repository and Pages destination after verification.

## Implementation

- [x] Add country-scoping and period-label tests, including Hong Kong/mainland separation, annual/monthly dates, nulls, zeros and unordered observations.
- [x] Add reusable regional overview, stock comparisons, native-frequency macro charts, selected-series CSV download and source coverage. Every plotted/card value follows the reference period; source coverage is explicitly independent of that filter.
- [x] Present four dedicated market overviews and retain Global Dataset and all existing US detail tabs with their original route and component IDs.
- [x] Distinguish observation periods, source updates and acquisition timestamps. Expose retained-source failures. Label DAX gross total return when compared with price indices.
- [x] Update the English README with page coverage and frequency limitations. Run dashboard tests, protected-runtime verification, build and bounded rendered review of all four markets, filtering, country switching, empty ranges, downloads and a narrow viewport.
- [ ] Review the final diff, publish, verify the cloud workflow and live pages, then report only verified outcomes.

## Review focus

- Mainland China must never include Hong Kong observations, and Europe must include only DE/FR/GB.
- Annual dates must be displayed as years and never presented as current monthly macro releases.
- The latest card and its previous comparison must come from the selected series and selected period, retaining zero and excluding missing values.
- Europe country changes must update all national macro cards/charts consistently; market index comparisons remain explicitly regional.
- Empty ranges and source failures must remain visible; no fallback to out-of-range values or fabricated continuity.

## Execution evidence

- Baseline: 3 existing dashboard tests passed; local main matches remote `20d0d254f3bf1dd6dc362dd9cf830cd3526a76d1`.
- Work remains in the existing task checkout; the unrelated untracked `data/international_raw 2/` directory is preserved.
- Review ruling: keep the original US detail tabs instead of moving them into local component state. This preserves existing `jobs`, `markets`, `growth` and `data` links and reload behavior.
- Review fixes: annual plots use year labels; monthly plots carry monthly period labels; successful acquisition timestamps are not presented as failed-attempt check times. Regional selectors use shareable shell focus state.
- Verification: all 8 dashboard tests and 50 Python tests passed; protected-runtime verification passed for 240 files; installed-runtime and existing Vite production builds passed. The host has no npm command, so its Node test and Vite entry points were invoked directly.
- Rendered checks: US overview and existing jobs route; mainland China cards and index comparison; Europe national switch to France with reload persistence and annual year labels; Hong Kong daily chart and empty annual cards for a 2026-only range. A downloaded Hong Kong CSV contained 206 rows, only HSI/HK, dated 2026-01-02 through 2026-11-03. Browser console had no errors.
- Responsive check: repaired the existing date-controls overflow at 390px; page width stayed 390px and the authored filter grid measured 358px. Restored the normal viewport afterward.
- Follow-up scope: the user clarified money-lending numbers as Hong Kong non-bank licensed money-lender statistics and requested official websites first. Official Companies Registry sources were provided in chat; no loan-rate collector or unreviewed new dataset was added.
