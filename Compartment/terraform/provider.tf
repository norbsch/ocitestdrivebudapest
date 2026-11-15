# Credentials are read from the selected profile in ~/.oci/config.
provider "oci" {
  auth                = "APIKey"
  config_file_profile = var.oci_config_profile
  region              = var.home_region
}
