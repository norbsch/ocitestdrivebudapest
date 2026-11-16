# Uses the selected profile from the existing OCI CLI/SDK configuration.
# Keep API signing keys outside this repository.
provider "oci" {
  region              = var.region
  config_file_profile = var.config_file_profile
}
