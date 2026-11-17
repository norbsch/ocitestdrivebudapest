# Uses the selected profile from the existing OCI CLI/SDK configuration.
# Keep API signing keys outside this repository.
provider "oci" {
  region              = var.region
  auth                = var.auth_method
  config_file_profile = var.auth_method == "APIKey" ? var.config_file_profile : null
}
