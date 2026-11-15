# The only resource created by this configuration.
resource "oci_identity_compartment" "lab" {
  compartment_id = var.parent_compartment_ocid
  name           = var.compartment_name
  description    = var.compartment_description
  freeform_tags  = var.freeform_tags

  # True also makes an existing-name collision fail instead of being adopted.
  enable_delete = var.enable_compartment_delete
}
