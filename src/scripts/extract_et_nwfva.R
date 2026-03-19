#!/usr/bin/env Rscript
# Extract yield tables from et.nwfva for growpy ingestion.
#
# Usage: Rscript extract_et_nwfva.R <output_csv>
#
# et.nwfva provides modern yield tables for NW Germany (2021):
#   - Eiche (Quercus robur), Buche (Fagus sylvatica), Fichte (Picea abies),
#     Douglasie (Pseudotsuga menziesii), Kiefer (Pinus sylvestris)
#
# API: et_tafel(art, bon, alter) - NOT vectorized, single alter per call.
#   bon = relative site index [-2..4] (integer), alter = age (single value)
#   Returns: data.frame with Alter, Hg, H100, Dg, V, etc.
#
# Output CSV columns:
#   species_latin, age, height, dbh, volume, region, management, site_index, table_id

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript extract_et_nwfva.R <output_csv>")
}
output_csv <- args[1]

if (!requireNamespace("et.nwfva", quietly = TRUE)) {
  stop("et.nwfva package not installed. Install with:\n  install.packages('et.nwfva', repos='https://cloud.r-project.org')")
}

library(et.nwfva)

species_configs <- list(
  list(code = "ei",  latin = "Quercus robur"),
  list(code = "bu",  latin = "Fagus sylvatica"),
  list(code = "fi",  latin = "Picea abies"),
  list(code = "dgl", latin = "Pseudotsuga menziesii"),
  list(code = "ki",  latin = "Pinus sylvestris")
)

ages <- seq(20, 160, by = 5)
bon_range <- -2:4

results <- data.frame(
  species_latin = character(),
  age = numeric(),
  height = numeric(),
  dbh = numeric(),
  volume = numeric(),
  region = character(),
  management = character(),
  site_index = numeric(),
  table_id = character(),
  stringsAsFactors = FALSE
)

cat("Processing et.nwfva yield tables...\n")

for (sp in species_configs) {
  cat(sprintf("  %s (%s):", sp$latin, sp$code))

  for (bon in bon_range) {
    rows_for_bon <- list()

    for (a in ages) {
      tryCatch({
        yt <- et_tafel(art = sp$code, bon = bon, alter = a)
        if (is.null(yt) || nrow(yt) < 1) next

        h <- yt$H100[1]
        d <- yt$Dg[1]
        v <- yt$V[1]

        if (is.na(h) || h <= 0) next

        rows_for_bon[[length(rows_for_bon) + 1]] <- data.frame(
          species_latin = sp$latin,
          age = a,
          height = h,
          dbh = ifelse(is.na(d), 0, d),
          volume = ifelse(is.na(v), 0, v),
          region = "DE-NW",
          management = "staggered_thinning",
          site_index = bon,
          table_id = paste0("nwfva_", sp$code, "_bon", bon),
          stringsAsFactors = FALSE
        )
      }, error = function(e) {
        # bon/alter out of range for this species - skip
      })
    }

    if (length(rows_for_bon) >= 2) {
      results <- rbind(results, do.call(rbind, rows_for_bon))
      cat(sprintf(" bon%d(%d)", bon, length(rows_for_bon)))
    }
  }
  cat("\n")
}

cat(sprintf("\nExtracted %d rows for %d species from %d unique tables\n",
            nrow(results),
            length(unique(results$species_latin)),
            length(unique(results$table_id))))

write.csv(results, output_csv, row.names = FALSE)
cat(sprintf("Wrote %s\n", output_csv))
