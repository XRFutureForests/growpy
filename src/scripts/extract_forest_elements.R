#!/usr/bin/env Rscript
# Extract yield tables from ForestElementsR for growpy ingestion.
#
# Usage: Rscript extract_forest_elements.R <output_csv>
#
# Output CSV columns:
#   species_latin, age, height, dbh, volume, region, management, site_index, table_id
#
# ForestElementsR provides classical German yield tables as named objects
# (fe_ytable_*) with matrix values indexed by age x site_index.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript extract_forest_elements.R <output_csv>")
}
output_csv <- args[1]

if (!requireNamespace("ForestElementsR", quietly = TRUE)) {
  stop("ForestElementsR package not installed. Install with:\n  install.packages('ForestElementsR', repos='https://cloud.r-project.org')")
}

library(ForestElementsR)

# Map yield table names to Latin species names
table_species <- list(
  "fe_ytable_beech_gehrhardt_moderate_1908" = "Fagus sylvatica",
  "fe_ytable_beech_wiedemann_moderate_1931" = "Fagus sylvatica",
  "fe_ytable_spruce_assmann_franz_mean_yield_level_1963" = "Picea abies",
  "fe_ytable_spruce_gehrhardt_moderate_1921" = "Picea abies",
  "fe_ytable_spruce_guttenberg_1915" = "Picea abies",
  "fe_ytable_spruce_vanselow_1951" = "Picea abies",
  "fe_ytable_spruce_wiedemann_moderate_1936_42" = "Picea abies",
  "fe_ytable_pine_gehrhardt_moderate_1921" = "Pinus sylvestris",
  "fe_ytable_pine_wiedemann_moderate_1943" = "Pinus sylvestris",
  "fe_ytable_oak_juettner_moderate_1955" = "Quercus robur",
  "fe_ytable_douglas_schober_moderate_1956" = "Pseudotsuga menziesii",
  "fe_ytable_silver_fir_hausser_moderate_1956" = "Abies alba",
  "fe_ytable_larch_schober_moderate_1946" = "Larix decidua",
  "fe_ytable_japanlarch_schober_moderate_1953" = "Larix kaempferi",
  "fe_ytable_birch_schwappach_1903_29" = "Betula pendula",
  "fe_ytable_blackalder_mitscherlich_heavy_1945" = "Alnus glutinosa",
  "fe_ytable_ash_wimmenauer_1919_29" = "Fraxinus excelsior",
  "fe_ytable_poplar_blume_1949" = "Populus x canescens",
  "fe_ytable_redoak_bauer_1955" = "Quercus rubra"
)

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

cat("Processing ForestElementsR yield tables...\n")

for (tname in names(table_species)) {
  latin <- table_species[[tname]]

  tryCatch({
    yt <- get(tname, envir = asNamespace("ForestElementsR"))

    if (!inherits(yt, "fe_yield_table")) next

    ages <- yt$age_coverage
    si_values <- yt$site_indexes
    vals <- yt$values

    # Find height matrix (h_q_m preferred)
    h_mat <- NULL
    for (candidate in c("h_q_m", "h_q_m_si_plus_025")) {
      if (candidate %in% names(vals)) {
        h_mat <- vals[[candidate]]
        break
      }
    }

    # Find DBH matrix (d_q_cm)
    d_mat <- NULL
    for (candidate in c("d_q_cm")) {
      if (candidate %in% names(vals)) {
        d_mat <- vals[[candidate]]
        break
      }
    }

    # Find volume matrix
    v_mat <- NULL
    for (candidate in c("v_m3_ha", "red_v_m3_ha")) {
      if (candidate %in% names(vals)) {
        v_mat <- vals[[candidate]]
        break
      }
    }

    if (is.null(h_mat) && is.null(d_mat)) {
      cat(sprintf("  Skipping %s: no height or DBH data\n", tname))
      next
    }

    # Extract management from table name
    mgmt <- "normal"
    if (grepl("moderate|maessig", yt$name_orig, ignore.case = TRUE)) mgmt <- "moderate_thinning"
    if (grepl("heavy|stark", yt$name_orig, ignore.case = TRUE)) mgmt <- "heavy_thinning"

    region <- "DE"

    cat(sprintf("  %s: %d ages x %d site indices\n", tname, length(ages), length(si_values)))

    for (si_idx in seq_along(si_values)) {
      si_val <- si_values[si_idx]

      heights <- if (!is.null(h_mat)) h_mat[, si_idx] else rep(0, length(ages))
      dbhs <- if (!is.null(d_mat)) d_mat[, si_idx] else rep(0, length(ages))
      vols <- if (!is.null(v_mat)) v_mat[, si_idx] else rep(0, length(ages))

      valid <- !is.na(ages) & !is.na(heights) & heights > 0
      if (sum(valid) < 2) next

      # Site index: use the height at a reference age if available
      # For German tables, use the h_q_m value as the site index metric
      si_height <- si_val

      row_data <- data.frame(
        species_latin = latin,
        age = ages[valid],
        height = heights[valid],
        dbh = dbhs[valid],
        volume = vols[valid],
        region = region,
        management = mgmt,
        site_index = si_height,
        table_id = paste0("fe_", gsub("fe_ytable_", "", tname), "_si", si_val),
        stringsAsFactors = FALSE
      )
      results <- rbind(results, row_data)
    }
  }, error = function(e) {
    cat(sprintf("  Warning: skipped %s: %s\n", tname, e$message))
  })
}

cat(sprintf("\nExtracted %d rows for %d species from %d unique tables\n",
            nrow(results),
            length(unique(results$species_latin)),
            length(unique(results$table_id))))

write.csv(results, output_csv, row.names = FALSE)
cat(sprintf("Wrote %s\n", output_csv))
