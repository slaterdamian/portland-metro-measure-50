# setup.R -- install the R analysis + cartography stack.
# Run:  Rscript setup.R   (or paste into an R console)
#
# R is used for geoprocessing + 2D choropleths; Python (pydeck) handles the 3D
# extruded "skyline" render. sf bundles its own GDAL/GEOS/PROJ on Windows, so it
# is independent of the conda `vpa` environment.

pkgs <- c(
  "sf",          # vector geoprocessing
  "tmap",        # thematic / choropleth maps
  "ggplot2",     # general plotting
  "dplyr",       # data manipulation
  "readr",       # fast CSV IO
  "rmapshaper",  # geometry simplification for web/3D
  "rayshader",   # optional native R 3D extrusion
  "scales",      # number formatting
  "here",        # project-relative paths
  "yaml"         # read config/paths.yml
)

new <- pkgs[!pkgs %in% rownames(installed.packages())]
if (length(new)) {
  install.packages(new, repos = "https://cloud.r-project.org")
}

cat("R packages ready.\n")
cat("sf bundled GDAL:", sf::sf_extSoftVersion()[["GDAL"]], "\n")
