# Authentication material is read from the attendee's external OCI profile.
provider "oci" {
  region              = var.region
  auth                = var.auth_method
  config_file_profile = var.auth_method == "APIKey" ? var.config_file_profile : null
}
