# Credentials are read from the selected profile in ~/.oci/config.
provider "oci" {
  auth                = var.auth
  config_file_profile = var.auth == "APIKey" ? var.config_file_profile : null
  region              = var.home_region
}
